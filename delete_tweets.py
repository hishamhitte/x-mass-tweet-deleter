import json
import time
import os
import sys
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Constants
PROGRESS_FILE = 'progress.json'

def load_tweet_ids(filepath):
    print(f"Loading tweets from {filepath}...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # The file usually starts with 'window.YTD.tweets.part0 = '
            prefix = 'window.YTD.tweets.part0 = '
            if content.startswith(prefix):
                content = content[len(prefix):]
            
            data = json.loads(content)
            tweet_ids = []
            for item in data:
                if 'tweet' in item and 'id_str' in item['tweet']:
                    tweet_ids.append(item['tweet']['id_str'])
            
            print(f"Found {len(tweet_ids)} tweets in the archive.")
            return tweet_ids
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('deleted_ids', []))
    return set()

def save_progress(deleted_ids):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'deleted_ids': list(deleted_ids)}, f)

def delete_tweet(page, tweet_id):
    url = f"https://x.com/i/status/{tweet_id}"
    
    try:
        # Navigate and wait for basic DOM
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Give it a second to render React components
        page.wait_for_timeout(1000)
        
        # 1. Check if the tweet is already deleted / not found
        not_found_texts = [
            "Hmm...this page doesn’t exist", 
            "This post has been deleted", 
            "This Post is unavailable.",
            "This Post is from an account that no longer exists."
        ]
        for text in not_found_texts:
            if page.locator(f"text={text}").count() > 0:
                print(" -> Tweet already deleted or not found. Skipping.")
                return "SKIPPED"

        # Wait for the main tweet article to load
        try:
            page.wait_for_selector('article[data-testid="tweet"]', timeout=6000)
        except PlaywrightTimeoutError:
            # Double check if it's a "Not found" page that loaded late
            for text in not_found_texts:
                if page.locator(f"text={text}").count() > 0:
                    print(" -> Tweet already deleted or not found. Skipping.")
                    return "SKIPPED"
            
            # Check for rate limit indicators
            if page.locator("text=Something went wrong").count() > 0 or page.locator("text=Retry").count() > 0:
                print(" -> 'Something went wrong' UI error detected. Likely Rate Limited.")
                return "RATE_LIMIT"
                
            print(" -> Could not load tweet page properly. Assuming rate limit.")
            return "RATE_LIMIT"

        # 2. Try to find the EXACT tweet article on the page using its ID
        target_tweet = page.locator(f'article:has(a[href*="{tweet_id}"])')
        
        if target_tweet.count() > 0:
            # SCENARIO A: Standard Tweet or Reply authored by you
            print(" -> Detected as standard Tweet/Reply. Opening menu...")
            caret_btn = target_tweet.first.locator('[data-testid="caret"]')
            if caret_btn.count() > 0:
                caret_btn.first.click()
                page.wait_for_timeout(1000)
                
                delete_menu_item = page.locator('div[role="menuitem"]:has-text("Delete")')
                if delete_menu_item.count() > 0:
                    delete_menu_item.first.click()
                    page.wait_for_timeout(1000)
                    
                    confirm_delete_btn = page.locator('[data-testid="confirmationSheetConfirm"]')
                    if confirm_delete_btn.count() > 0:
                        confirm_delete_btn.first.click()
                        page.wait_for_timeout(1500)
                        print(" -> Tweet deleted successfully.")
                        return "DELETED"
                    else:
                        print(" -> Error: Failed to find Delete confirmation button.")
                        return "ERROR"
                else:
                    print(" -> Error: No 'Delete' option in menu. (Unexpected state)")
                    page.mouse.click(0, 0)
                    return "ERROR"
            else:
                print(" -> Error: Could not find the 3-dots menu on this specific tweet.")
                return "ERROR"
                
        else:
            # SCENARIO B: Tweet ID not in DOM. 
            # This happens if it's a Repost (X redirects to original tweet) OR if it's already deleted.
            
            # X fetches retweet state asynchronously. Give it up to 3 seconds to turn the button green.
            try:
                page.wait_for_selector('[data-testid="unretweet"]', timeout=3000)
            except PlaywrightTimeoutError:
                pass # If it times out, it might be already un-retweeted, a deleted thread, or a Ghost Retweet.
                
            unretweet_btn = page.locator('[data-testid="unretweet"]')
            if unretweet_btn.count() > 0:
                print(" -> Detected as an active Repost. Clicking 'Undo repost'...")
                unretweet_btn.first.click()
                page.wait_for_timeout(1000)
                
                confirm_btn = page.locator('[data-testid="unretweetConfirm"]')
                if confirm_btn.count() > 0:
                    confirm_btn.first.click()
                    page.wait_for_timeout(1500)
                    print(" -> Repost undone successfully.")
                    return "DELETED"
                else:
                    print(" -> Error: Failed to find 'Undo repost' confirm dropdown.")
                    return "ERROR"
            else:
                # Is it a ghost retweet? (A known X bug where old retweets appear as gray/un-retweeted)
                retweet_btn = page.locator('[data-testid="retweet"]')
                if retweet_btn.count() > 0:
                    print(" -> Repost icon is gray. X does not recognize this as retweeted by you anymore. Skipping.")
                    return "SKIPPED"
                else:
                    # Not a ghost repost (no retweet button), and our tweet ID is not on the page.
                    print(" -> Tweet not found on page (likely already deleted). Skipping.")
                    return "SKIPPED"
        
    except Exception as e:
        print(f" -> Unexpected error interacting with page: {e}")
        return "ERROR"

def main():
    if len(sys.argv) < 2:
        print("Usage: python delete_tweets.py <path_to_tweets.js>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    
    # Load data
    all_tweet_ids = load_tweet_ids(filepath)
    deleted_ids = load_progress()
    print(f"Already processed {len(deleted_ids)} tweets based on progress file.")
    
    tweets_to_delete = [tid for tid in all_tweet_ids if tid not in deleted_ids]
    print(f"Tweets remaining to process: {len(tweets_to_delete)}")
    
    if not tweets_to_delete:
        print("No tweets left to process. You are done!")
        sys.exit(0)
        
    print("\n" + "="*50)
    print("Connecting to your active Edge browser...")
    print("="*50 + "\n")
    
    with sync_playwright() as p:
        try:
            # Connect to the running Edge instance on port 9222
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            # Get the first active context (your session)
            context = browser.contexts[0]
            # Create a new tab for the script to use
            page = context.new_page()
        except Exception as e:
            print(f"Failed to connect to Edge: {e}")
            print("\nMake sure you started Edge using the command in the README and are logged into X!")
            sys.exit(1)

        print("Successfully connected to your browser!")
        print("Starting deletion process (DO NOT close the automated tab)...\n")
        
        try:
            for idx, tweet_id in enumerate(tweets_to_delete):
                print(f"[{idx+1}/{len(tweets_to_delete)}] Processing tweet {tweet_id}...")
                
                while True:
                    status = delete_tweet(page, tweet_id)
                    
                    if status in ["DELETED", "SKIPPED"]:
                        deleted_ids.add(tweet_id)
                        save_progress(deleted_ids)
                        break
                    elif status == "RATE_LIMIT":
                        print(" -> Rate Limit Hit! Pausing for 10 minutes before retrying this tweet...")
                        time.sleep(10 * 60)
                        print(" -> 10 minutes elapsed. Retrying...")
                        continue
                    else:
                        print(" -> Will skip and try this one again on the next run.")
                        break
                        
                # Only apply the human-like delay if we actually deleted something
                if status == "DELETED":
                    time.sleep(random.uniform(2.0, 5.0))
                    
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Progress has been saved.")
            # Use os._exit to forcefully terminate immediately. 
            # Playwright's event loop often hangs if you try to gracefully close pages after a Ctrl+C thread interrupt.
            os._exit(0)
        except Exception as e:
            print(f"\nAn error occurred: {e}. Progress has been saved.")
            os._exit(1)

if __name__ == "__main__":
    main()
