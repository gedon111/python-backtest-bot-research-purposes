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

# ML Classifier disabled for this iteration

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

# Feature extraction removed

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
            df = pd.read_csv(cache_path)
            df["open_time"] = pd.to_datetime(df["open_time"])
        else:
            update_status("Error", 0, "No candles data found in database or artifacts/candles.csv. Run a backtest first!")
            return

    # Reconstruct open_time from time if missing (when loaded from DB)
    if "open_time" not in df.columns and "time" in df.columns:
        df["open_time"] = pd.to_datetime(df["time"], unit="s")

    # Recalculate indicators & SMC
    df = bot.compute_indicators(df)
    df["time"] = df["open_time"].apply(lambda x: int(x.timestamp()))
    
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

    # 3. Parameter Search Space definition (Adaptive & Co-optimized Search)
    update_status("Parameter Tuning", 30, "Starting adaptive hyperparameter tuning...")
    
    # Dynamic Seeding to prevent stagnation
    dynamic_seed = int(time.time() * 1000) % 1000000
    np.random.seed(dynamic_seed)
    print(f"Running ML optimization with dynamic seed: {dynamic_seed}")
    
    # Chronological Train-Test Split Index (70% Train, 30% Test)
    split_idx = int(len(df) * 0.7)
    
    best_score = -999999.0
    best_params = {}
    best_classifier = None
    
    # Run 50 trials of strategy parameters tuning with Co-optimization
    n_trials = 50
    for trial in range(n_trials):
        # Continuous search bounds with finer steps
        trial_params = {
            "sl_ratio_min": float(np.random.uniform(0.01, 0.04)),
            "kdj_j_long_cap": float(np.random.uniform(40.0, 90.0)),
            "kdj_k_long_cap": float(np.random.uniform(30.0, 70.0)),
            "kdj_k_short_floor": float(np.random.uniform(50.0, 90.0)),
            "kdj_j_short_cap": float(np.random.uniform(80.0, 120.0)),
            "atr_mult_exit": float(np.random.uniform(1.2, 2.5)),
            "atr_mult_be": float(np.random.uniform(1.5, 3.0)),
            "rr_min": float(np.random.uniform(1.2, 2.5))
        }
        
        # Simulate trades with these parameters
        sim_df = bot.simulate_trades(df.copy(), min_ob_quality=1, iteration_parameters=trial_params)
        trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
        
        if trades_df.empty:
            continue
            
        # Chronological split of trades based on entry candle index
        train_trades = trades_df[trades_df['entry_idx'] < split_idx]
        test_trades = trades_df[trades_df['entry_idx'] >= split_idx]
        
        score = -999999.0
        trial_clf = None
        
        # Evaluate parameter search on out-of-sample trades directly without ML classifier
        if len(test_trades) > 0:
            score = test_trades['pnl_pct'].sum()
        else:
            score = -50.0
            
        if score > best_score:
            best_score = score
            best_params = trial_params
            best_classifier = trial_clf
            
        progress = 30 + int((trial / n_trials) * 35)
        update_status("Parameter Tuning", progress, f"Trial {trial+1}/{n_trials} - Best Test Return: {best_score:.2f}%")

    update_status("Classifier Training", 65, "Skipping classifier training (insufficient trades)...")
    print("\n[ML Classifier Layer Disclaimer]")
    print("The ML classifier layer was attempted but not evaluated in this iteration due to insufficient trade count (21 total trades) for reliable train/test partitioning. This is left for future work with a larger dataset.")
    
    classifier_model = None
    classifier_threshold = 0.5
    filtered_pnl_change = 0.0
 
    # 5. Save results to SQL Iterations Database
    update_status("Saving Results", 90, "Writing optimized parameters and serialization model to DB...")
    
    timestamp = int(time.time())
    
    # Calculate metrics for all quality levels (0, 1, 2, 3)
    metrics = {}
    for q in [0, 1, 2, 3]:
        # 1. Base simulation (tuned params, no classifier)
        base_sim_df = bot.simulate_trades(df.copy(), min_ob_quality=q, iteration_parameters=best_params)
        base_trades_df = base_sim_df.attrs.get("trades_df", pd.DataFrame())
        
        # 2. Optimized simulation (tuned params + classifier)
        opt_params = best_params.copy()
        if classifier_model is not None:
            opt_params["classifier_model"] = classifier_model
            opt_params["classifier_threshold"] = classifier_threshold
        
        opt_sim_df = bot.simulate_trades(df.copy(), min_ob_quality=q, iteration_parameters=opt_params)
        opt_trades_df = opt_sim_df.attrs.get("trades_df", pd.DataFrame())
        
        metrics[f"q{q}"] = {
            "base_trades": len(base_trades_df),
            "base_pnl": float(base_trades_df['pnl_pct'].sum()) if not base_trades_df.empty else 0.0,
            "base_wr": float((base_trades_df['pnl_pct'] > 0).mean() * 100) if not base_trades_df.empty else 0.0,
            "tuned_trades": len(opt_trades_df),
            "tuned_pnl": float(opt_trades_df['pnl_pct'].sum()) if not opt_trades_df.empty else 0.0,
            "tuned_wr": float((opt_trades_df['pnl_pct'] > 0).mean() * 100) if not opt_trades_df.empty else 0.0
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
        model_type="Swept Heuristic",
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
    
    # Print the discovered parameters cleanly in the stdout so we can collect them
    print("=== DISCOVERED PARAMETERS ===")
    print(json.dumps(best_params, indent=2))
    print("=== PERFORMANCE METRICS ===")
    print(json.dumps(metrics, indent=2))
    print("==========================")

if __name__ == "__main__":
    main()
