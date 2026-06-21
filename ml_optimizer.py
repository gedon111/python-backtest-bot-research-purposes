import os
import sys
import json
import time
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
import db_manager

# Ensure dependencies are available
try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    print("[ERROR] scikit-learn is not installed. Please run: pip install scikit-learn")
    sys.exit(1)

# Import our bot module
sys.path.append(os.path.abspath("."))
import importlib.util
spec = importlib.util.spec_from_file_location("bot", "Binance backtest bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

def update_status(phase, progress, log=""):
    status = {
        "phase": phase,
        "progress": int(progress),
        "log": log,
        "timestamp": int(time.time())
    }
    os.makedirs("artifacts", exist_ok=True)
    with open("artifacts/ml_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else f"ML Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    prev_iteration_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    update_status("Initializing", 5, "Connecting to database...")
    db_url = db_manager.get_db_url()
    engine = db_manager.init_db(db_url)
    session = db_manager.get_session(engine)
    
    # 1. Fetch candles from database
    update_status("Loading Data", 15, "Loading candles and historical order blocks...")
    candles_query = "SELECT * FROM candles ORDER BY time ASC"
    df = pd.read_sql(candles_query, engine)
    if df.empty:
        # Fallback to local csv cache if database is empty
        csv_path = "artifacts/candles.csv"
        if os.path.isfile(csv_path):
            df = pd.read_csv(csv_path)
            df["open_time"] = pd.to_datetime(df["open_time"])
        else:
            update_status("Error", 0, "No candles data found in database or artifacts/candles.csv. Run a backtest first!")
            return

    # Reconstruct open_time from time if missing (when loaded from DB)
    if "open_time" not in df.columns and "time" in df.columns:
        df["open_time"] = pd.to_datetime(df["time"], unit="s")

    # Recalculate indicators & SMC
    df = bot.compute_indicators(df)
    
    # 2. Get error feedback weight mappings from previous iteration if specified
    error_weights = {}
    if prev_iteration_id is not None:
        update_status("Loading Error Feedback", 20, f"Analyzing failed trades of iteration {prev_iteration_id}...")
        try:
            prev_trades = pd.read_sql(
                f"SELECT entry_time, pnl_pct FROM trades WHERE min_ob_quality = {prev_iteration_id}", 
                engine
            )
            # Find losses (false positives)
            losses = prev_trades[prev_trades["pnl_pct"] <= 0]
            for t_time in losses["entry_time"]:
                error_weights[int(t_time)] = 3.0
            print(f"Loaded {len(error_weights)} loss entry patterns to reweight.")
        except Exception as e:
            print(f"Warning: Could not load previous iteration data: {e}")

    # 3. Parameter Search Space definition (Optuna / Randomized Search)
    update_status("Parameter Tuning", 30, "Starting randomized hyperparameter tuning...")
    np.random.seed(42)
    
    best_score = -999999.0
    best_params = {}
    
    # Run 50 trials of strategy parameters tuning
    n_trials = 50
    for trial in range(n_trials):
        trial_params = {
            "sl_ratio_min": float(np.random.choice([0.015, 0.02, 0.025, 0.03])),
            "kdj_j_long_cap": float(np.random.choice([50.0, 60.0, 70.0, 80.0])),
            "kdj_k_long_cap": float(np.random.choice([40.0, 50.0, 60.0])),
            "kdj_k_short_floor": float(np.random.choice([60.0, 70.0, 80.0])),
            "kdj_j_short_cap": float(np.random.choice([90.0, 100.0, 110.0])),
            "atr_mult_exit": float(np.random.choice([1.4, 1.6, 1.8, 2.0])),
            "atr_mult_be": float(np.random.choice([1.8, 2.0, 2.2, 2.4])),
            "rr_min": float(np.random.choice([1.3, 1.5, 1.7, 2.0]))
        }
        
        # Simulate trades with these parameters
        sim_df = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=trial_params)
        stats = sim_df.attrs.get("trade_stats", {})
        
        total_trades = stats.get("Total Trades", 0)
        net_return = stats.get("Total Net Return (%)", 0.0)
        win_rate = stats.get("Win Rate (%)", 0.0)
        
        # Objective: Maximize return, penalize runs with very few trades (overfitting)
        score = net_return
        if total_trades < 10:
            score -= (10 - total_trades) * 5.0
            
        if score > best_score:
            best_score = score
            best_params = trial_params
            
        progress = 30 + int((trial / n_trials) * 35)
        update_status("Parameter Tuning", progress, f"Trial {trial+1}/{n_trials} - Best Net Return: {best_score:.2f}%")

    update_status("Classifier Training", 65, "Tuned parameters found. Staging classifier features...")
    
    # 4. Generate final trades using best parameters to train classifier
    sim_df = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=best_params)
    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
    
    classifier_model = None
    classifier_threshold = 0.5
    filtered_pnl_change = 0.0
    
    features_list = []
    labels_list = []
    sample_weights = []
    
    if not trades_df.empty:
        # Build features dataset for RandomForest training
        for _, trade in trades_df.iterrows():
            entry_idx = int(trade['entry_idx'])
            if entry_idx >= len(df):
                continue
                
            entry_time = int(df.at[entry_idx, 'time'])
            
            # Extract features at entry
            feats = [
                float(df.at[entry_idx, 'MACD']),
                float(df.at[entry_idx, 'MACD_signal']),
                float(df.at[entry_idx, 'MACD_hist']),
                float(df.at[entry_idx, 'K']),
                float(df.at[entry_idx, 'D']),
                float(df.at[entry_idx, 'J']),
                float(df.at[entry_idx, 'ATR']),
                float(df.at[entry_idx, 'ATR_200']),
                float(df.at[entry_idx, 'volume_ma_ratio']),
                float(df.at[entry_idx, 'taker_buy_ratio']),
                float(df.at[entry_idx, 'body_wick_ratio']),
                float(df.at[entry_idx, 'time_hour']),
                float(df.at[entry_idx, 'time_day_of_week']),
                float(trade.get('entry_ob_quality', 1.0))
            ]
            
            label_val = 1 if trade['pnl_pct'] > 0 else 0
            
            # Weight boosting for previous iteration failures
            weight = error_weights.get(entry_time, 1.0)
            
            features_list.append(feats)
            labels_list.append(label_val)
            sample_weights.append(weight)

        X = np.array(features_list)
        y = np.array(labels_list)
        weights = np.array(sample_weights)
        
        # Train RandomForest classifier
        update_status("Classifier Training", 75, "Training Random Forest classifier on entry setups...")
        classifier_model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        classifier_model.fit(X, y, sample_weight=weights)
        
        # Score trades probability
        probs = classifier_model.predict_proba(X)[:, 1]
        
        # Calculate what would happen if we filter out trades with win prob < 50%
        in_sample_taken = probs >= 0.5
        filtered_trades = trades_df[in_sample_taken]
        
        original_net = trades_df['pnl_pct'].sum()
        filtered_net = filtered_trades['pnl_pct'].sum()
        filtered_pnl_change = filtered_net - original_net
        
        print(f"ML Classifier entry filter improved Net Return by {filtered_pnl_change:.2f}% in-sample.")
    else:
        print("No trades generated during optimized sweep to train classifier.")

    # 5. Save results to SQL Iterations Database
    update_status("Saving Results", 90, "Writing optimized parameters and serialization model to DB...")
    
    # Save the model to a local pickle file
    timestamp = int(time.time())
    
    # Create iteration record
    # We query the database to get the next iteration ID (or let database autoincrement do it, then update)
    # To do it cleanly, we commit a blank record first or use raw connection
    metrics = {
        "original_trades": len(trades_df),
        "original_pnl_pct": float(trades_df['pnl_pct'].sum()) if not trades_df.empty else 0.0,
        "original_win_rate": float((trades_df['pnl_pct'] > 0).mean() * 100) if not trades_df.empty else 0.0,
        "optimized_trades": len(filtered_trades) if classifier_model else len(trades_df),
        "optimized_pnl_pct": float(filtered_trades['pnl_pct'].sum()) if classifier_model else float(trades_df['pnl_pct'].sum()) if not trades_df.empty else 0.0,
        "optimized_win_rate": float((filtered_trades['pnl_pct'] > 0).mean() * 100) if classifier_model else float((trades_df['pnl_pct'] > 0).mean() * 100) if not trades_df.empty else 0.0
    }
    
    pattern_diff = {
        "tuned_parameters": best_params,
        "pnl_improvement_pct": filtered_pnl_change,
        "reweighted_failures_count": len(error_weights)
    }
    
    # Serialize overrides into JSON string
    parameters_dict = best_params.copy()
    parameters_dict["classifier_threshold"] = classifier_threshold
    
    # Define a temporary entry to retrieve iteration_id
    new_iteration = db_manager.MLIteration(
        label=label,
        created_at=timestamp,
        model_type="RandomForestClassifier",
        parameters=json.dumps(parameters_dict),
        metrics=json.dumps(metrics),
        pattern_diff=json.dumps(pattern_diff)
    )
    session.add(new_iteration)
    session.commit()
    
    iteration_id = new_iteration.iteration_id
    
    # Save model file
    if classifier_model:
        os.makedirs("artifacts/models", exist_ok=True)
        model_path = f"artifacts/models/model_iter_{iteration_id}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(classifier_model, f)
        
        # Save model path relative
        parameters_dict["classifier_model_path"] = model_path
        new_iteration.parameters = json.dumps(parameters_dict)
        session.commit()
        
    update_status("Complete", 100, f"ML optimization completed successfully! Iteration ID: {iteration_id}")
    print(f"\nOptimization complete! Iteration ID {iteration_id} saved to DB.")

if __name__ == "__main__":
    main()
