#!/usr/bin/env python3
"""
Auto-Retraining Script for UFC Fight Predictor

This script orchestrates the entire pipeline:
1. Scrapes new fights since last update
2. Processes and cleans the new data
3. Reprocesses features for affected fighters
4. Retrains the model
5. Validates the new model
6. Sends notifications

Usage:
    .venv/bin/python auto_retrain.py [--force-full-scrape] [--skip-scrape] [--dry-run]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.scrape_incremental import get_last_scraped_date, scrape_new_fights
from utils.incremental_processing import (
    get_last_processed_date, 
    process_new_fights_only,
    needs_full_reprocess
)


# Configure logging
def setup_logging(log_dir='logs'):
    """Set up logging to file and console"""
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'auto_retrain_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return log_file


def run_scraper(force_full=False):
    """
    Run the incremental scraper.
    
    Args:
        force_full: If True, scrapes all fights from scratch
    
    Returns:
        Number of new fights scraped
    """
    logging.info("="*70)
    logging.info("STEP 1: SCRAPING NEW FIGHTS")
    logging.info("="*70)
    
    try:
        if force_full:
            logging.info("Force full scrape enabled - scraping all fights")
            last_date = None
        else:
            last_date = get_last_scraped_date()
            
        new_fights = scrape_new_fights(last_date)
        
        logging.info(f"✓ Scraping completed: {new_fights} new fights added")
        return new_fights
        
    except Exception as e:
        logging.error(f"✗ Scraping failed: {e}")
        raise


def run_data_processing():
    """
    Process new raw data and append to cleaned dataset.
    
    Returns:
        Number of new fights processed
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 2: PROCESSING NEW DATA")
    logging.info("="*70)
    
    try:
        last_processed = get_last_processed_date()
        new_processed = process_new_fights_only(last_processed_date=last_processed)
        
        logging.info(f"✓ Processing completed: {new_processed} new fights processed")
        return new_processed
        
    except Exception as e:
        logging.error(f"✗ Data processing failed: {e}")
        raise


def run_feature_engineering(force=False):
    """
    Run feature engineering on the full dataset.
    This computes weighted averages, ELO ratings, etc.
    
    Returns:
        True if successful
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 3: FEATURE ENGINEERING")
    logging.info("="*70)
    
    try:
        # Check if we need full reprocessing
        if force:
            logging.info("Force feature engineering enabled")

        if force or needs_full_reprocess():
            logging.info("Running full feature engineering (process_fights_alpha.py)")
            
            # Run as subprocess to avoid import conflicts
            import subprocess
            result = subprocess.run(
                [sys.executable, 'process_fights_alpha.py'],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                logging.info("✓ Feature engineering completed")
                return True
            else:
                logging.error(f"Feature engineering failed with exit code {result.returncode}")
                if result.stderr:
                    logging.error(f"Error output: {result.stderr[:500]}")
                raise Exception("Feature engineering subprocess failed")
        else:
            logging.info("✓ Feature engineering up to date - skipping")
            return True
            
    except Exception as e:
        logging.error(f"✗ Feature engineering failed: {e}")
        logging.error("You may need to run process_fights_alpha.py manually")
        raise


def run_model_training(skip_hyperparameter_tuning=True):
    """
    Train the LGBM model on the updated dataset.
    
    Args:
        skip_hyperparameter_tuning: If True, uses existing best params
    
    Returns:
        Model accuracy on test set
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 4: MODEL TRAINING")
    logging.info("="*70)
    
    try:
        # Backup existing model artifacts
        artifact_dirs = ['saved_models', 'saved_preprocessing']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        for model_dir in artifact_dirs:
            if not os.path.exists(model_dir):
                continue

            backup_dir = f'{model_dir}/backup_{timestamp}'
            logging.info(f"Backing up existing artifacts from {model_dir} to {backup_dir}")
            os.makedirs(backup_dir, exist_ok=True)

            import shutil
            for file in os.listdir(model_dir):
                if file.endswith(('.txt', '.pkl', '.joblib', '.json')):
                    src = os.path.join(model_dir, file)
                    dst = os.path.join(backup_dir, file)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)

        logging.info("Training final production model (this may take several minutes)...")

        command = [sys.executable, 'train_final_model.py']
        if os.path.exists(os.path.join('data', 'best_params.json')):
            command.extend(['--params', os.path.join('data', 'best_params.json')])
        
        # Train through today; the scraper only adds completed fights it can find.
        command.extend(['--train-through', datetime.now().strftime('%Y-%m-%d')])
        
        import subprocess
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            logging.info("✓ Final model training completed")
            if result.stdout:
                logging.info(result.stdout[-1000:])
            return None
        else:
            logging.error(f"Model training failed: {result.stderr}")
            raise Exception("Model training failed")
            
    except Exception as e:
        logging.error(f"✗ Model training failed: {e}")
        raise


def validate_model(min_training_rows=500):
    """
    Validate that the production model artifacts were written correctly.
    
    Args:
        min_training_rows: Minimum acceptable number of training rows
    
    Returns:
        True if model passes validation
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 5: MODEL VALIDATION")
    logging.info("="*70)
    
    try:
        required_files = [
            'saved_models/lgbm_single_model.joblib',
            'saved_models/lgbm_single_model_metadata.json',
            'saved_preprocessing/label_encoder_single.joblib',
            'saved_preprocessing/selected_columns_single.json',
        ]

        missing = [path for path in required_files if not os.path.exists(path)]
        if missing:
            logging.error(f"Missing model artifacts: {missing}")
            return False

        with open('saved_models/lgbm_single_model_metadata.json', 'r') as f:
            metadata = json.load(f)

        training_rows = metadata.get('training_rows', 0)
        feature_columns = metadata.get('feature_columns', 0)
        max_feature_date = metadata.get('max_feature_date_used')

        logging.info(f"Training rows: {training_rows}")
        logging.info(f"Feature columns: {feature_columns}")
        logging.info(f"Max feature date used: {max_feature_date}")

        if training_rows < min_training_rows:
            logging.warning(
                f"Model trained on only {training_rows} rows; minimum is {min_training_rows}"
            )
            return False

        if feature_columns == 0:
            logging.warning("Model has no feature columns")
            return False

        logging.info("✓ Model artifact validation passed")
        return True
        
    except Exception as e:
        logging.error(f"✗ Model validation failed: {e}")
        return False


def run_odds_scraper():
    """
    Scrape betting odds for all fights.
    
    Returns:
        Success status
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 5a: SCRAPING BETTING ODDS")
    logging.info("="*70)
    
    try:
        import subprocess
        
        logging.info("Running UFC.com odds scraper...")

        ufc_result = subprocess.run(
            [sys.executable, 'scrapers/scrape_fights_with_odds.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        success = False
        if ufc_result.returncode == 0:
            logging.info("✓ UFC.com odds scraping completed successfully")
            success = True
        else:
            logging.warning(f"⚠ UFC.com odds scraping failed with exit code {ufc_result.returncode}")
            if ufc_result.stderr:
                logging.warning(f"Error: {ufc_result.stderr[:200]}")

        logging.info("Running BestFightOdds missing-odds backfill...")
        bfo_result = subprocess.run(
            [
                sys.executable,
                'scrapers/backfill_bestfightodds.py',
                '--report',
                os.path.join('data', 'bestfightodds_backfill_report.json'),
            ],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=900  # 15 minute timeout
        )

        if bfo_result.returncode == 0:
            logging.info("✓ BestFightOdds backfill completed successfully")
            if bfo_result.stdout:
                logging.info(bfo_result.stdout[-1000:])
            success = True
        else:
            logging.warning(f"⚠ BestFightOdds backfill failed with exit code {bfo_result.returncode}")
            if bfo_result.stderr:
                logging.warning(f"Error: {bfo_result.stderr[:500]}")

        return success

    except subprocess.TimeoutExpired:
        logging.warning("⚠ Odds scraping/backfill timed out")
        return False
        
    except Exception as e:
        logging.warning(f"⚠ Odds scraping failed: {e}")
        logging.warning("Continuing without odds update...")
        return False


def run_backtesting():
    """
    Run backtesting on recent fights to validate model performance.
    
    Returns:
        Dictionary with backtest results
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 5b: BACKTESTING MODEL PERFORMANCE")
    logging.info("="*70)
    
    try:
        import subprocess
        from datetime import datetime, timedelta
        
        # Calculate date range for backtesting (last 1 year)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        logging.info(f"Running backtest from {start_str} to {end_str}...")
        
        summary_path = os.path.join('test_results', 'no_leakage_backtest_summary.json')

        # Run leakage-safe rolling evaluator with date range arguments
        result = subprocess.run(
            [
                sys.executable,
                'testing/no_leakage_backtest.py',
                '--start-date',
                start_str,
                '--end-date',
                end_str,
                '--output-dir',
                'test_results',
            ],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=900  # 15 minute timeout
        )
        
        if result.returncode == 0:
            if not os.path.exists(summary_path):
                logging.info("✓ Backtesting completed (summary file missing)")
                return {'success': True}

            with open(summary_path, 'r') as f:
                summary = json.load(f)

            bankroll = summary.get('final_bankroll')
            profit_pct = summary.get('profit_pct')
            accuracy = summary.get('accuracy')
            predicted_fights = summary.get('predicted_fights')
            skipped_fights = summary.get('skipped_fights')

            logging.info(f"✓ Leakage-safe backtesting completed")
            logging.info(f"  Predicted fights: {predicted_fights}")
            logging.info(f"  Skipped fights: {skipped_fights}")
            if accuracy is not None:
                logging.info(f"  Accuracy: {accuracy:.4f}")
            if bankroll is not None and profit_pct is not None:
                logging.info(f"  Final bankroll: ${bankroll:.2f}")
                logging.info(f"  Profit: {profit_pct:+.2f}%")

            for warning in summary.get('strict_coverage_messages', []):
                logging.warning(f"Coverage warning: {warning}")

            return {
                'success': True,
                'bankroll': bankroll,
                'profit_pct': profit_pct,
                'accuracy': accuracy,
                'predicted_fights': predicted_fights,
                'skipped_fights': skipped_fights,
            }
        else:
            logging.warning(f"⚠ Backtesting failed with exit code {result.returncode}")
            if result.stderr:
                logging.warning(f"Error: {result.stderr[:200]}")
            return {'success': False}
        
    except subprocess.TimeoutExpired:
        logging.warning("⚠ Backtesting timed out after 5 minutes")
        return {'success': False, 'error': 'timeout'}
        
    except Exception as e:
        logging.warning(f"⚠ Backtesting failed: {e}")
        return {'success': False, 'error': str(e)}


def send_notification(status, message, log_file):
    """
    Send notification about retraining status.
    Can be extended to send email, Slack, etc.
    
    Args:
        status: 'success' or 'failure'
        message: Summary message
        log_file: Path to log file
    """
    logging.info("\n" + "="*70)
    logging.info("STEP 6: NOTIFICATION")
    logging.info("="*70)
    
    emoji = "✓" if status == "success" else "✗"
    logging.info(f"{emoji} Auto-retraining {status}: {message}")
    logging.info(f"Log file: {log_file}")
    
    # TODO: Add email/Slack notification here
    # Example:
    # send_email(subject=f"UFC Model Retraining {status}", body=message)
    # send_slack(message=f"{emoji} {message}")


def main():
    """Main orchestration function"""
    parser = argparse.ArgumentParser(description='Auto-retrain UFC Fight Predictor')
    parser.add_argument('--force-full-scrape', action='store_true',
                       help='Scrape all fights from scratch')
    parser.add_argument('--skip-scrape', action='store_true',
                       help='Skip scraping step (use for testing)')
    parser.add_argument('--skip-training', action='store_true',
                       help='Skip model training (for testing pipeline)')
    parser.add_argument('--force-process', action='store_true',
                       help='Force processing even if no new scrapes (useful after fixing bugs)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without making changes')
    
    args = parser.parse_args()
    
    # Setup logging
    log_file = setup_logging()
    
    logging.info("╔" + "="*68 + "╗")
    logging.info("║" + " "*15 + "UFC FIGHT PREDICTOR AUTO-RETRAIN" + " "*21 + "║")
    logging.info("║" + " "*20 + f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*21 + "║")
    logging.info("╚" + "="*68 + "╝")
    
    try:
        # Step 1: Scrape new fights
        if not args.skip_scrape:
            new_fights = run_scraper(force_full=args.force_full_scrape)
            
            if new_fights == 0 and not args.force_full_scrape and not args.force_process:
                logging.info("\n" + "="*70)
                logging.info("NO NEW FIGHTS - Skipping remaining steps")
                logging.info("="*70)
                send_notification('success', 'No new fights to process', log_file)
                return 0
        else:
            logging.info("Skipping scraping step (--skip-scrape)")
            new_fights = 1  # Assume there's new data
        
        if args.force_process:
            logging.info("Force processing enabled - will process even without new scrapes")
        
        # Step 2: Process new data
        new_processed = run_data_processing()
        
        if new_processed == 0 and not args.force_process:
            logging.info("\n" + "="*70)
            logging.info("NO NEW DATA TO PROCESS")
            logging.info("="*70)
            send_notification('success', 'No new data processed', log_file)
            return 0
        
        # Step 3: Feature engineering
        run_feature_engineering(force=args.force_process or args.force_full_scrape)
        
        # Step 4: Train model
        if not args.skip_training:
            accuracy = run_model_training()
        else:
            logging.info("Skipping model training (--skip-training)")
            accuracy = None
        
        # Step 5: Validate model
        validation_passed = validate_model()
        
        # Step 5a: Scrape betting odds for new fights
        run_odds_scraper()
        
        # Step 5b: Run backtesting
        backtest_results = run_backtesting()
        
        # Step 6: Send notification
        if validation_passed:
            msg = f"Successfully retrained model with {new_fights} new fights"
            if accuracy:
                msg += f" (Accuracy: {accuracy:.4f})"
            if backtest_results and backtest_results.get('success') and 'profit_pct' in backtest_results:
                msg += f", Backtest profit: {backtest_results['profit_pct']:+.2f}%"
            send_notification('success', msg, log_file)
        else:
            send_notification('failure', 'Model validation failed', log_file)
            return 1
        
        logging.info("\n" + "╔" + "="*68 + "╗")
        logging.info("║" + " "*18 + "AUTO-RETRAIN COMPLETED SUCCESSFULLY" + " "*15 + "║")
        logging.info("║" + " "*20 + f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*20 + "║")
        logging.info("╚" + "="*68 + "╝\n")
        
        return 0
        
    except KeyboardInterrupt:
        logging.info("\n\nInterrupted by user")
        send_notification('failure', 'Interrupted by user', log_file)
        return 1
        
    except Exception as e:
        logging.error(f"\n\nFATAL ERROR: {e}", exc_info=True)
        send_notification('failure', str(e), log_file)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
