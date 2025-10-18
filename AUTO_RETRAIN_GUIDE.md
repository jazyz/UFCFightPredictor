# Auto-Retraining System Guide

## Overview

The auto-retraining system enables **automatic incremental updates** to your UFC Fight Predictor without manually rescraping everything from scratch. It runs on a schedule (via cron) and:

1. ✅ Scrapes only **new fights** since last update
2. ✅ Processes and cleans the new data
3. ✅ Recomputes features for affected fighters
4. ✅ Retrains the LGBM model
5. ✅ Validates model performance
6. ✅ Logs everything for monitoring

---

## Quick Start

### 1. Make Scripts Executable

```bash
chmod +x setup_cron.sh
chmod +x auto_retrain.py
```

### 2. Test Manual Run

Before scheduling, test that everything works:

```bash
python auto_retrain.py
```

This will:
- Check for new fights since your last scrape (December 16, 2023)
- Process any new fights found
- Retrain the model
- Show you detailed logs

### 3. Schedule Automatic Updates

Run the interactive setup:

```bash
./setup_cron.sh
```

Choose your schedule:
- **Weekly** (recommended for UFC's event frequency)
- **Twice per week** (Mon/Fri)
- **Daily**
- **Custom**

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────┐
│           auto_retrain.py (Orchestrator)        │
└─────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ Scraper │   │ Processor│   │ Training │
   └─────────┘   └──────────┘   └──────────┘
```

### Incremental Scraping

**File**: `scrapers/scrape_incremental.py`

**What it does**:
1. Reads `data/fight_details_date.csv` to find the last scraped date
2. Scrapes UFC stats for events **after** that date
3. **Appends** new fights to the CSV (doesn't overwrite)

**Key functions**:
- `get_last_scraped_date()` - Finds most recent fight in dataset
- `get_new_events(last_date)` - Fetches only new events
- `scrape_new_fights()` - Main scraping function

### Incremental Processing

**File**: `utils/incremental_processing.py`

**What it does**:
1. Reads new fights from raw data
2. Applies transformations (ratios, times, filtering)
3. **Appends** to `data/modified_fight_details.csv`

**Transformations applied**:
- Converts "x of y" to numbers and percentages
- Converts "m:ss" to decimal minutes
- Filters out women's fights and draws
- Removes duplicate columns

### Feature Engineering

**File**: `process_fights_alpha.py` (existing script)

**What it does**:
- Recomputes ELO ratings chronologically
- Generates 180+ features per fight
- Creates weighted averages of fighter stats
- Outputs to `data/detailed_fights.csv`

**Note**: This step processes the **entire** dataset to maintain chronological integrity for ELO ratings and career statistics.

### Model Training

**File**: `ml_alpha_date.py` (existing script)

**What it does**:
- Trains LightGBM on full dataset
- Uses data augmentation (red/blue swapping)
- Applies feature pruning
- Saves model to `saved_models/`

---

## Command Line Options

### Basic Usage

```bash
python auto_retrain.py
```

### Advanced Options

```bash
# Skip scraping (testing only)
python auto_retrain.py --skip-scrape

# Force scrape all fights from scratch
python auto_retrain.py --force-full-scrape

# Skip training (test pipeline only)
python auto_retrain.py --skip-training

# Dry run (preview without changes)
python auto_retrain.py --dry-run
```

---

## Logging & Monitoring

### Log Files

All runs are logged to: `logs/auto_retrain_YYYYMMDD_HHMMSS.log`

View the latest log:
```bash
ls -t logs/auto_retrain_*.log | head -1 | xargs cat
```

Watch logs in real-time:
```bash
tail -f logs/cron_output.log
```

### Log Format

```
2024-01-15 02:00:01 [INFO] Starting incremental scraper
2024-01-15 02:00:05 [INFO] Found 3 new events to scrape
2024-01-15 02:01:23 [INFO] ✓ Scraped 28 new fights
2024-01-15 02:01:45 [INFO] ✓ Processed 28 new fights
2024-01-15 02:15:32 [INFO] ✓ Model trained - Accuracy: 0.6412
```

---

## Cron Management

### View Current Cron Jobs

```bash
crontab -l
```

### Edit Cron Jobs Manually

```bash
crontab -e
```

### Remove All Cron Jobs

```bash
crontab -r
```

### Common Cron Schedules

```bash
# Every Monday at 2 AM
0 2 * * 1

# Monday and Friday at 2 AM  
0 2 * * 1,5

# Daily at 2 AM
0 2 * * *

# Every 6 hours
0 */6 * * *

# First day of each month at 3 AM
0 3 1 * *
```

---

## Troubleshooting

### No New Fights Found

**Symptom**: "No new fights to scrape. Database is up to date!"

**Cause**: Your data is current, or UFC hasn't had events recently.

**Solution**: This is normal! The system will automatically check next time.

---

### Scraping Fails

**Symptom**: HTTP errors or timeout errors

**Possible causes**:
- UFC Stats website is down
- Internet connection issues
- Rate limiting

**Solution**: 
```bash
# Retry manually
python auto_retrain.py

# Check UFC stats site
curl -I http://ufcstats.com/statistics/events/completed?page=all
```

---

### Processing Errors

**Symptom**: "Data processing failed"

**Possible causes**:
- CSV format changed
- Corrupt data

**Solution**:
```bash
# Check the raw data
head -20 data/fight_details_date.csv

# Try processing manually
python utils/incremental_processing.py
```

---

### Model Training Fails

**Symptom**: "Model training failed"

**Possible causes**:
- Insufficient data
- Feature engineering didn't run
- Missing dependencies

**Solution**:
```bash
# Check if detailed_fights.csv exists and is recent
ls -lh data/detailed_fights.csv

# Run feature engineering manually
python process_fights_alpha.py

# Check Python dependencies
pip install -r requirements.txt
```

---

### Cron Job Not Running

**Symptom**: No new logs in `logs/cron_output.log`

**Possible causes**:
- Cron service not running
- Wrong paths in crontab
- Python environment issues

**Solution**:
```bash
# Check if cron is running (macOS)
sudo launchctl list | grep cron

# Test command manually
cd /path/to/UFCFightPredictor && python auto_retrain.py

# Check cron logs (if available)
grep CRON /var/log/system.log

# Re-run setup
./setup_cron.sh
```

---

## Notifications (Optional)

### Email Notifications

Add to `auto_retrain.py` in the `send_notification()` function:

```python
import smtplib
from email.mime.text import MIMEText

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'your-email@gmail.com'
    msg['To'] = 'your-email@gmail.com'
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('your-email@gmail.com', 'your-app-password')
        server.send_message(msg)
```

### Slack Notifications

```python
import requests

def send_slack(message):
    webhook_url = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    requests.post(webhook_url, json={'text': message})
```

---

## Best Practices

### 1. **Monitor Regularly**

Check logs weekly:
```bash
tail -50 logs/cron_output.log
```

### 2. **Backup Your Data**

Before major updates:
```bash
cp -r data/ data_backup_$(date +%Y%m%d)/
cp -r saved_models/ saved_models_backup_$(date +%Y%m%d)/
```

### 3. **Keep Models Versioned**

The system automatically backs up models before retraining to:
```
saved_models/backup_YYYYMMDD_HHMMSS/
```

### 4. **Validate After Updates**

After retraining, check:
- Model accuracy (should be ~64%)
- Number of fights processed
- No errors in logs

### 5. **UFC Event Schedule**

UFC typically has events every 1-2 weeks. A **weekly** cron schedule is optimal.

---

## File Structure

```
UFCFightPredictor/
├── auto_retrain.py              # Main orchestration script
├── setup_cron.sh                # Cron setup helper
├── scrapers/
│   ├── scrape_incremental.py    # New incremental scraper
│   └── scrape_all_fights.py     # Old full scraper (kept for reference)
├── utils/
│   ├── incremental_processing.py # Incremental data processing
│   └── __init__.py
├── logs/
│   ├── auto_retrain_*.log       # Detailed run logs
│   └── cron_output.log          # Cron stdout/stderr
├── data/
│   ├── fight_details_date.csv   # Raw scraped fights
│   ├── modified_fight_details.csv # Processed fights
│   └── detailed_fights.csv      # Engineered features
└── saved_models/
    ├── backup_*/                # Automatic model backups
    └── *.pkl                    # Current models
```

---

## Performance

### Typical Runtime

- **Scraping**: 2-5 minutes (for 1-2 events)
- **Processing**: < 1 minute
- **Feature Engineering**: 5-10 minutes
- **Model Training**: 10-20 minutes
- **Total**: ~20-35 minutes

### Resource Usage

- **CPU**: Moderate during training
- **Memory**: ~2-4 GB
- **Disk**: +10-20 MB per event
- **Network**: Minimal (only scraping)

---

## Next Steps

1. **Test the system**:
   ```bash
   python auto_retrain.py --skip-training
   ```

2. **Schedule it**:
   ```bash
   ./setup_cron.sh
   ```

3. **Monitor first run**:
   Check logs after the scheduled time

4. **Optional enhancements**:
   - Add email/Slack notifications
   - Set up model performance tracking
   - Create dashboard for monitoring

---

## FAQ

**Q: Will this interfere with manual model training?**  
A: No, but avoid running both simultaneously. The system backs up models before retraining.

**Q: Can I run this on a different machine?**  
A: Yes! Just update the paths in `setup_cron.sh` and ensure Python dependencies are installed.

**Q: What if I want to force a full rescrape?**  
A: Run `python auto_retrain.py --force-full-scrape`

**Q: How do I disable auto-retraining temporarily?**  
A: Comment out the cron line: `crontab -e` then add `#` before the line.

**Q: Does this work with the ensemble model?**  
A: Currently uses `ml_alpha_date.py`. You can modify `auto_retrain.py` to use `ml_ensemble.py` instead.

---

## Support

For issues or questions:
1. Check the logs: `logs/auto_retrain_*.log`
2. Run with verbose output: `python auto_retrain.py`
3. Test individual components:
   - `python scrapers/scrape_incremental.py`
   - `python utils/incremental_processing.py`

Happy auto-retraining! 🥊🤖
