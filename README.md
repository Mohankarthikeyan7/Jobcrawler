# UK Company Job Crawler

An automated job crawler that searches UK company websites for DevOps, Cloud, and Infrastructure engineering positions and sends notifications via Telegram.

## Features

- 🔍 Automatically finds company official websites
- 🎯 Searches for career pages on company websites
- 💼 Detects job openings for DevOps/Cloud/Infrastructure roles
- 📱 Sends real-time notifications via Telegram
- 🔄 Runs every 15 minutes via GitHub Actions
- 📊 Tracks processed companies to avoid duplicates
- 🛡️ Handles errors gracefully and skips problematic sites

## Job Types Detected

- DevOps Engineer
- Senior DevOps Engineer
- Cloud Engineer
- Senior Cloud Engineer
- Infrastructure Engineer
- Senior Infrastructure Engineer

## Setup Instructions

### 1. Create a Telegram Bot

1. Message @BotFather on Telegram
2. Send `/newbot` and follow the instructions
3. Save the bot token (looks like `123456789:ABCdefGhIjKlMnOpQrStUvWxYz`)
4. Get your chat ID by messaging @userinfobot or:
   - Send a message to your bot
   - Visit `https://api.telegram.org/bot<YourBOTToken>/getUpdates`
   - Find your chat ID in the response

### 2. Setup GitHub Repository

1. Fork or create a new repository with these files
2. Add your Excel file named `companies.xlsx` to the repository root
3. Go to Settings → Secrets and variables → Actions
4. Add the following secrets:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from step 1
   - `TELEGRAM_CHAT_ID`: Your chat ID from step 1

### 3. Excel File Format

Your `companies.xlsx` file should have company names in the first column:

| Company Name |
|--------------|
| Acme Corp    |
| Tech Solutions Ltd |
| Digital Innovations |
| Cloud Systems UK |

### 4. Enable GitHub Actions

1. Go to the Actions tab in your repository
2. Enable workflows if prompted
3. The crawler will start running automatically every 10 minutes

### 5. Manual Execution

You can also trigger the crawler manually:
1. Go to Actions → UK Company Job Crawler
2. Click "Run workflow"
3. Optionally specify the number of companies to process

## Configuration

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID
- `EXCEL_FILE`: Path to Excel file (default: `companies.xlsx`)

### Crawler Settings

You can modify these in `job_crawler.py`:

```python
# Number of companies to process per run
max_companies = 10

# Job keywords to search for
job_keywords = [
    'devops engineer',
    'senior devops engineer',
    'cloud engineer',
    'senior cloud engineer',
    'infrastructure engineer',
    'senior infrastructure engineer'
]

# Career page indicators
career_indicators = [
    'careers', 'career', 'jobs', 'job', 
    'work-with-us', 'join-us', 'opportunities'
]
```

## How It Works

1. **Company Website Discovery**: Tries common domain patterns for each company
2. **Career Page Detection**: Searches for career/jobs pages on company websites
3. **Job Matching**: Scans career pages for relevant engineering positions
4. **Notification**: Sends Telegram alerts when matching jobs are found
5. **Progress Tracking**: Maintains a list of processed companies in `processed_companies.json`

## Monitoring

### Telegram Notifications

You'll receive notifications for:
- 🎉 Job alerts when relevant positions are found
- 📊 Summary reports after each crawling session
- ❌ Error notifications if something goes wrong

### GitHub Actions Logs

- Check the Actions tab for detailed execution logs
- Logs are uploaded as artifacts and retained for 30 days
- The `processed_companies.json` file is automatically committed back to the repo

## Troubleshooting

### Common Issues

1. **No notifications received**:
   - Check your Telegram bot token and chat ID
   - Ensure secrets are properly set in GitHub
   - Verify the bot can send messages to your chat

2. **Companies not being processed**:
   - Check if Excel file exists and is properly formatted
   - Review GitHub Actions logs for errors
   - Companies might not have discoverable websites

3. **Rate limiting**:
   - The crawler includes delays between requests
   - If rate limited, it will skip problematic companies

### Logs and Debugging

- All activities are logged with timestamps
- Errors are gracefully handled and logged
- Check Actions artifacts for detailed logs

## Customization

### Adding More Job Types

Edit the `job_keywords` list in `job_crawler.py`:

```python
self.job_keywords = [
    'devops engineer',
    'site reliability engineer',
    'platform engineer',
    # Add your keywords here
]
```

### Changing Crawling Frequency

Edit the cron schedule in `.github/workflows/job-crawler.yml`:

```yaml
schedule:
  - cron: '*/30 * * * *'  # Every 30 minutes
  - cron: '0 */2 * * *'   # Every 2 hours
  - cron: '0 9,17 * * *'  # 9 AM and 5 PM daily
```

### Processing More Companies

Change the `max_companies` parameter in the workflow or when running manually.

## Legal and Ethical Considerations

- The crawler respects robots.txt files
- Includes delays between requests to avoid overwhelming servers
- Only searches publicly available career pages
- Gracefully handles errors and skips problematic sites

## Support

If you encounter issues:
1. Check the GitHub Actions logs
2. Review your Telegram bot setup
3. Ensure your Excel file is properly formatted
4. Check that all secrets are correctly configured

## License

This project is provided as-is for educational and personal use.
