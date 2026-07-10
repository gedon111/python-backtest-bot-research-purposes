import os

filepath = "export_gui_data.py"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

original_crlf = ("\r\n" in code)
code = code.replace("\r\n", "\n")

# 1. Update imports and add global state
target_1 = """import numpy as np
import pandas as pd
import db_manager"""

rep_1 = """import numpy as np
import pandas as pd
import db_manager
import pickle
import time

SELECTED_ITERATION_ID = 0"""

target_1 = target_1.replace("\r\n", "\n")
rep_1 = rep_1.replace("\r\n", "\n")

if target_1 in code:
    code = code.replace(target_1, rep_1)
    print("Patch 1 applied!")
else:
    print("Patch 1 not found!")

# 2. Add extra Candle fields to SQLite database save logic
target_2 = """                macd_signal=float(row['macd_signal']) if pd.notnull(row['macd_signal']) else None,
                macd_hist=float(row['macd_hist']) if pd.notnull(row['macd_hist']) else None,
                k=float(row['k']) if pd.notnull(row['k']) else None,
                d=float(row['d']) if pd.notnull(row['d']) else None,
                j=float(row['j']) if pd.notnull(row['j']) else None,
                atr_14=float(row['atr_14']) if pd.notnull(row['atr_14']) else None,
                atr_200=float(row['atr_200']) if pd.notnull(row['atr_200']) else None"""

# Note: The database save keys in export_gui_data.py actually use uppercase for some fields if they are read from base_df
# Let's inspect the target:
# In export_gui_data.py (around lines 280-297):
#                 macd=float(row['MACD']) if pd.notnull(row['MACD']) else None,
#                 macd_signal=float(row['MACD_signal']) if pd.notnull(row['MACD_signal']) else None,
#                 macd_hist=float(row['MACD_hist']) if pd.notnull(row['MACD_hist']) else None,
#                 k=float(row['K']) if pd.notnull(row['K']) else None,
#                 d=float(row['D']) if pd.notnull(row['D']) else None,
#                 j=float(row['J']) if pd.notnull(row['J']) else None,
#                 atr_14=float(row['ATR']) if pd.notnull(row['ATR']) else None,
#                 atr_200=float(row['ATR_200']) if pd.notnull(row['ATR_200']) else None

target_2 = """                macd=float(row['MACD']) if pd.notnull(row['MACD']) else None,
                macd_signal=float(row['MACD_signal']) if pd.notnull(row['MACD_signal']) else None,
                macd_hist=float(row['MACD_hist']) if pd.notnull(row['MACD_hist']) else None,
                k=float(row['K']) if pd.notnull(row['K']) else None,
                d=float(row['D']) if pd.notnull(row['D']) else None,
                j=float(row['J']) if pd.notnull(row['J']) else None,
                atr_14=float(row['ATR']) if pd.notnull(row['ATR']) else None,
                atr_200=float(row['ATR_200']) if pd.notnull(row['ATR_200']) else None"""

rep_2 = """                macd=float(row['MACD']) if pd.notnull(row['MACD']) else None,
                macd_signal=float(row['MACD_signal']) if pd.notnull(row['MACD_signal']) else None,
                macd_hist=float(row['MACD_hist']) if pd.notnull(row['MACD_hist']) else None,
                k=float(row['K']) if pd.notnull(row['K']) else None,
                d=float(row['D']) if pd.notnull(row['D']) else None,
                j=float(row['J']) if pd.notnull(row['J']) else None,
                atr_14=float(row['ATR']) if pd.notnull(row['ATR']) else None,
                atr_200=float(row['ATR_200']) if pd.notnull(row['ATR_200']) else None,
                volume_ma_ratio=float(row['volume_ma_ratio']) if pd.notnull(row.get('volume_ma_ratio')) else None,
                taker_buy_ratio=float(row['taker_buy_ratio']) if pd.notnull(row.get('taker_buy_ratio')) else None,
                body_wick_ratio=float(row['body_wick_ratio']) if pd.notnull(row.get('body_wick_ratio')) else None,
                time_hour=int(row['time_hour']) if pd.notnull(row.get('time_hour')) else None,
                time_day_of_week=int(row['time_day_of_week']) if pd.notnull(row.get('time_day_of_week')) else None"""

target_2 = target_2.replace("\r\n", "\n")
rep_2 = rep_2.replace("\r\n", "\n")

if target_2 in code:
    code = code.replace(target_2, rep_2)
    print("Patch 2 applied!")
else:
    print("Patch 2 not found!")

# 3. Server ThreadingTCPServer and endpoints replacement
target_3 = """    # Start local web server and open browser
    PORT = 8765
    HOST = "127.0.0.1"
    
    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    print(f"\\n[Dashboard] Starting local web server on http://{HOST}:{PORT} ...")
    
    def serve():
        with socketserver.TCPServer((HOST, PORT), SilentHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()"""

rep_3 = """    # Start local web server and open browser
    PORT = 8765
    HOST = "127.0.0.1"
    
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/api/iterations":
                self.handle_get_iterations()
            elif self.path == "/api/run_ml/status":
                self.handle_get_ml_status()
            else:
                super().do_GET()

        def do_POST(self):
            if self.path == "/api/run_ml":
                self.handle_run_ml()
            elif self.path == "/api/iterations/update_label":
                self.handle_update_label()
            elif self.path == "/api/iterations/select":
                self.handle_select_iteration()
            elif self.path == "/api/push_gsheet":
                self.handle_push_gsheet()
            else:
                self.send_error(404, "Endpoint not found")

        def handle_get_iterations(self):
            try:
                engine = db_manager.init_db()
                session = db_manager.get_session(engine)
                iterations = session.query(db_manager.MLIteration).order_by(db_manager.MLIteration.iteration_id.asc()).all()
                data = []
                for it in iterations:
                    data.append({
                        "iteration_id": it.iteration_id,
                        "label": it.label,
                        "created_at": it.created_at,
                        "model_type": it.model_type,
                        "parameters": json.loads(it.parameters),
                        "metrics": json.loads(it.metrics),
                        "pattern_diff": json.loads(it.pattern_diff)
                    })
                session.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                self.send_error(500, f"Database error: {e}")

        def handle_get_ml_status(self):
            status_path = "artifacts/ml_status.json"
            status = {"phase": "Idle", "progress": 0, "log": "Optimizer is ready."}
            if os.path.isfile(status_path):
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        status = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))

        def handle_run_ml(self):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                params = json.loads(body) if body else {}
                label = params.get("label", "RandomForest Run")
                prev_id = params.get("prev_iteration_id")
                
                # Check status
                status_path = "artifacts/ml_status.json"
                if os.path.isfile(status_path):
                    try:
                        with open(status_path, "r", encoding="utf-8") as f:
                            curr = json.load(f)
                            if curr.get("phase") not in ["Complete", "Error", "Idle"] and time.time() - curr.get("timestamp", 0) < 60:
                                self.send_response(409)
                                self.send_header("Content-Type", "application/json")
                                self.end_headers()
                                self.wfile.write(json.dumps({"error": "ML Optimizer is already running."}).encode("utf-8"))
                                return
                    except Exception:
                        pass
                
                import subprocess
                import sys
                def run_optimizer():
                    cmd = [sys.executable, "ml_optimizer.py", label]
                    if prev_id is not None:
                        cmd.append(str(prev_id))
                    try:
                        subprocess.run(cmd, check=True)
                    except Exception as e:
                        err_status = {"phase": "Error", "progress": 0, "log": f"Execution failed: {e}", "timestamp": int(time.time())}
                        with open("artifacts/ml_status.json", "w", encoding="utf-8") as sf:
                            json.dump(err_status, sf, indent=2)
                
                threading.Thread(target=run_optimizer, daemon=True).start()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Started", "label": label}).encode("utf-8"))
            except Exception as e:
                self.send_error(500, f"Failed to start training: {e}")

        def handle_update_label(self):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                params = json.loads(body)
                it_id = int(params["iteration_id"])
                new_label = str(params["label"])
                
                engine = db_manager.init_db()
                session = db_manager.get_session(engine)
                iteration = session.query(db_manager.MLIteration).filter(db_manager.MLIteration.iteration_id == it_id).first()
                if iteration:
                    iteration.label = new_label
                    session.commit()
                    session.close()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "Success"}).encode("utf-8"))
                else:
                    session.close()
                    self.send_error(404, "Iteration not found")
            except Exception as e:
                self.send_error(500, f"Error updating label: {e}")

        def handle_select_iteration(self):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                params = json.loads(body)
                it_id = int(params["iteration_id"])
                
                iteration_parameters = None
                active_model = None
                
                if it_id > 0:
                    engine = db_manager.init_db()
                    session = db_manager.get_session(engine)
                    iteration = session.query(db_manager.MLIteration).filter(db_manager.MLIteration.iteration_id == it_id).first()
                    if not iteration:
                        session.close()
                        self.send_error(404, "Iteration not found")
                        return
                    
                    iteration_params = json.loads(iteration.parameters)
                    session.close()
                    
                    model_path = iteration_params.get("classifier_model_path")
                    if model_path and os.path.isfile(model_path):
                        try:
                            with open(model_path, "rb") as f:
                                active_model = pickle.load(f)
                        except Exception as e:
                            print(f"Error loading model: {e}")
                    
                    iteration_parameters = {
                        "sl_ratio_min": iteration_params.get("sl_ratio_min"),
                        "kdj_j_long_cap": iteration_params.get("kdj_j_long_cap"),
                        "kdj_k_long_cap": iteration_params.get("kdj_k_long_cap"),
                        "kdj_k_short_floor": iteration_params.get("kdj_k_short_floor"),
                        "kdj_j_short_cap": iteration_params.get("kdj_j_short_cap"),
                        "atr_mult_exit": iteration_params.get("atr_mult_exit"),
                        "atr_mult_be": iteration_params.get("atr_mult_be"),
                        "rr_min": iteration_params.get("rr_min"),
                        "classifier_model": active_model,
                        "classifier_threshold": iteration_params.get("classifier_threshold", 0.5)
                    }
                
                bot = load_bot_module()
                cache_path = "artifacts/candles.csv"
                if os.path.isfile(cache_path):
                    base_df = pd.read_csv(cache_path)
                    base_df["open_time"] = pd.to_datetime(base_df["open_time"])
                else:
                    base_df = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR)
                
                base_df = bot.compute_indicators(base_df)
                base_df["time"] = base_df["open_time"].apply(lambda x: int(x.timestamp()))
                
                levels = [0, 1, 2, 3]
                runs_by_threshold = {}
                threshold_runs = []
                sim_dfs = {}
                
                for level in levels:
                    sim_df = bot.simulate_trades(base_df.copy(), min_ob_quality=level, iteration_parameters=iteration_parameters)
                    sim_dfs[level] = sim_df
                    stats = sim_df.attrs.get("trade_stats", {})
                    trades_df = sim_df.attrs.get("trades_df", pd.DataFrame())
                    obs = bot.compute_smc(sim_df)
                    
                    trades = normalize_records(trades_df.to_dict(orient="records")) if not trades_df.empty else []
                    obs = normalize_records(obs)
                    stats = {k: to_native(v) for k, v in stats.items()}
                    
                    runs_by_threshold[level] = {
                        "obs": obs,
                        "trades": trades,
                        "stats": stats
                    }
                    threshold_runs.append({
                        "min_quality": level,
                        "trade_stats": stats,
                        "trade_count": len(trades),
                        "orderblock_count": len(obs)
                    })
                
                default_level = 1
                base_df["Trade_Status"] = sim_dfs[default_level]["Trade_Status"].fillna("")
                candles = normalize_records(base_df[["time", "open_time", "open", "high", "low", "close", "volume", "MACD", "MACD_signal", "MACD_hist", "K", "D", "J", "ATR", "ATR_200", "Trade_Status"]].to_dict(orient="records"))
                
                with open("artifacts/candles.json", "w", encoding="utf-8") as f:
                    json.dump(candles, f, indent=2, default=fallback_json)
                with open("artifacts/threshold_runs.json", "w", encoding="utf-8") as f:
                    json.dump(threshold_runs, f, indent=2, default=fallback_json)
                with open("artifacts/runs_by_threshold.json", "w", encoding="utf-8") as f:
                    json.dump(runs_by_threshold, f, indent=2, default=fallback_json)
                
                default_run = runs_by_threshold.get(default_level, runs_by_threshold[0])
                pd.DataFrame(default_run["trades"]).to_csv("artifacts/trades_default_view.csv", index=False)
                pd.DataFrame(default_run["obs"]).to_csv("artifacts/orderblocks_default_view.csv", index=False)
                
                global SELECTED_ITERATION_ID
                SELECTED_ITERATION_ID = it_id
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Success", "iteration_id": it_id}).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Error selecting iteration: {e}")

        def handle_push_gsheet(self):
            try:
                bot = load_bot_module()
                
                global SELECTED_ITERATION_ID
                it_id = SELECTED_ITERATION_ID
                
                iteration_parameters = None
                active_model = None
                
                if it_id > 0:
                    engine = db_manager.init_db()
                    session = db_manager.get_session(engine)
                    iteration = session.query(db_manager.MLIteration).filter(db_manager.MLIteration.iteration_id == it_id).first()
                    if iteration:
                        iteration_params = json.loads(iteration.parameters)
                        model_path = iteration_params.get("classifier_model_path")
                        if model_path and os.path.isfile(model_path):
                            try:
                                with open(model_path, "rb") as f:
                                    active_model = pickle.load(f)
                            except Exception:
                                pass
                        
                        iteration_parameters = {
                            "sl_ratio_min": iteration_params.get("sl_ratio_min"),
                            "kdj_j_long_cap": iteration_params.get("kdj_j_long_cap"),
                            "kdj_k_long_cap": iteration_params.get("kdj_k_long_cap"),
                            "kdj_k_short_floor": iteration_params.get("kdj_k_short_floor"),
                            "kdj_j_short_cap": iteration_params.get("kdj_j_short_cap"),
                            "atr_mult_exit": iteration_params.get("atr_mult_exit"),
                            "atr_mult_be": iteration_params.get("atr_mult_be"),
                            "rr_min": iteration_params.get("rr_min"),
                            "classifier_model": active_model,
                            "classifier_threshold": iteration_params.get("classifier_threshold", 0.5)
                        }
                    session.close()
                
                cache_path = "artifacts/candles.csv"
                if os.path.isfile(cache_path):
                    base_df = pd.read_csv(cache_path)
                    base_df["open_time"] = pd.to_datetime(base_df["open_time"])
                else:
                    base_df = bot.get_candles(symbol="BTCUSDT", interval=bot.Client.KLINE_INTERVAL_4HOUR)
                
                base_df = bot.compute_indicators(base_df)
                
                levels = [0, 1, 2, 3]
                sim_dfs = {}
                for level in levels:
                    sim_df = bot.simulate_trades(base_df.copy(), min_ob_quality=level, iteration_parameters=iteration_parameters)
                    sim_dfs[level] = sim_df
                
                print(f"[Dashboard Server] Exporting iteration {it_id} to Google Sheets...")
                bot.push_all_thresholds_to_gsheet(base_df.copy(), levels=levels, precomputed_dfs=sim_dfs)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "Success", "message": "Google Sheets updated."}).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Google Sheets Sync failed: {e}")

    print(f"\\n[Dashboard] Starting local web server on http://{HOST}:{PORT} ...")
    
    def serve():
        with ThreadingHTTPServer((HOST, PORT), SilentHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()"""

target_3 = target_3.replace("\r\n", "\n")
rep_3 = rep_3.replace("\r\n", "\n")

if target_3 in code:
    code = code.replace(target_3, rep_3)
    print("Patch 3 applied!")
else:
    # check for exact casing or spacing
    target_3_alt = """    # Start local web server and open browser
    PORT = 8765
    HOST = "127.0.0.1"
    
    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    print(f"\\n[Dashboard] Starting local web server on http://{HOST}:{PORT} ...")
    
    def serve():
        with socketserver.TCPServer((HOST, PORT), SilentHandler) as httpd:
            httpd.serve_forever()

    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()"""
    target_3_alt = target_3_alt.replace("\r\n", "\n")
    if target_3_alt in code:
        code = code.replace(target_3_alt, rep_3)
        print("Patch 3 (alt) applied!")
    else:
        print("Patch 3 not found!")

# Restore line endings
if original_crlf:
    code = code.replace("\n", "\r\n")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)
print("Successfully saved changes to export_gui_data.py!")
