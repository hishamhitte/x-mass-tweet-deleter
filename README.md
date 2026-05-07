# X (Twitter) Mass Tweet & Retweet Deletion Tool

A robust, local-first Python automation tool to programmatically mass delete your tweets and retweets using Microsoft Edge and Playwright. 

Unlike API-based tools that often result in `403 Forbidden` errors or API tier bans, this tool uses **UI-driven automation**. It attaches to your existing, authenticated browser session and manually clicks "Delete" or "Undo repost" on every single post in your archive, exactly as a human would.

## Prerequisites
- **Python 3.12+** installed on your system.
- **Microsoft Edge** browser (built into Windows).

---

## Setup Instructions

### 1. Request your X Data Archive (DO THIS FIRST)
Before you can run the script, you need your complete X history.
1. Go to your X Settings -> **Your account** -> **Download an archive of your data**.
2. Request the archive. **Note: This usually takes 24 to 48 hours for X to process and email to you.**
3. Once you receive the email, download and extract the `.zip` file. 
4. Look inside the extracted `data` folder and locate the `tweets.js` file. This contains all your tweet IDs.

### 2. Install Dependencies
Open a terminal in this directory and run:
```cmd
pip install -r requirements.txt
playwright install chromium
```

### 3. Launch Microsoft Edge in Debugging Mode
For the script to take control of your browser, you **must** start Edge with a special "remote debugging" flag. The script cannot connect to a normally opened Edge window.

1. Close **ALL** existing Microsoft Edge windows completely.
2. Press `Win + R` on your keyboard to open the Run dialog.
3. Paste the following exact command and press Enter:
   
   `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="C:\edge_debug"`

4. A brand new Edge window will open.
5. In this new window, go to [https://x.com](https://x.com) and log in to your account.

> [!WARNING]
> **Security Note:** Running Edge with the debugging port `9222` open allows local scripts to control your browser. Only use this specific browser session for this script, and close the browser completely when you are finished.

### 4. Run the Script
While the special Edge window is still open and logged into X, go back to your terminal and run the script, pointing it to the `tweets.js` file you extracted in Step 1:

```cmd
python delete_tweets.py "C:\path\to\your\extracted\data\tweets.js"
```

The script will open a new tab in your Edge browser and begin systematically deleting your history. Do not close this automated tab!

---

## Features
- **Background Execution:** You can completely minimize both the terminal and the Edge browser while the script is running. You can lock your PC, switch user accounts, or use your computer for other tasks without interrupting the deletion process!
- **Resumable:** Progress is automatically saved to `progress.json`. You can press `Ctrl+C` to stop the script at any time, and it will pick up exactly where it left off on the next run.
- **Rate Limit Handling:** X heavily restricts the number of actions you can take per hour. The script automatically detects UI rate limit errors ("Something went wrong") and will pause for 10 minutes before automatically resuming.
- **Human-like Delays:** Adds randomized delays between successful deletions to mimic human behavior and avoid triggering bot-detection systems.
- **Ghost Retweet Detection:** Automatically identifies and skips corrupted "Ghost Retweets" (see FAQ below).

---

## FAQ & Known Challenges

### Why does the script randomly pause for 10 minutes?
X implements strict rate-limiting to prevent bulk deletions. If you delete too many tweets too quickly, X's servers will block your actions and display a "Something went wrong" error. The script detects this and automatically pauses for 10 minutes to let your account cooldown before continuing. For massive archives (10k+ tweets), this process can take several days of running in the background.

### Why not use the official X API instead of automating the UI?
X has locked down its API and strictly monetized access. Attempting to bulk-delete thousands of tweets via standard API scripts or cURL requests now results in immediate `403 Forbidden` or `401 Unauthorized` errors. Using Playwright to physically click the buttons in your own browser session perfectly bypasses all API restrictions and prevents your account from being banned.

### What is a "Ghost Retweet" and why are some skipped?
If you have an older account or are deleting thousands of posts, you will likely encounter the legendary X "Ghost Retweet" bug. This is a severe caching issue on X's backend servers:
1. Your profile tweet count might say `16,000` tweets.
2. The retweets might still be visible if you scroll down your Mobile App timeline.
3. **However**, X's Web Server database has lost the index for these retweets. When the script navigates to the tweet on the web browser, the retweet button is completely **gray** (X thinks you haven't retweeted it).

Because the button is gray on the web, the script is physically blocked from undoing the retweet. It will intelligently log `Repost icon is gray. X does not recognize this as retweeted by you anymore` and skip it.

**How to fix the Ghost Retweet count:**
[I HAVE YET TO TEST THIS]Because this is a server-side corruption on X's end, the only known way to clear these phantom tweets and reset your profile count to zero is to **deactivate your X account** for a few days (do not exceed 29 days), and then reactivate it. During reactivation, X is forced to rebuild your database index from scratch, which drops the corrupted ghost references and corrects your tweet count.
