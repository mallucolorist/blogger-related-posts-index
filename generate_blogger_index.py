import requests
import json
import math

# --- Configuration ---
# IMPORTANT: Replace with your actual Blog URL (e.g., "yourblogname.blogspot.com")
BLOG_URL = "YOUR_BLOG_URL_HERE"
OUTPUT_FILE = "blog_index.json"
MAX_RESULTS_PER_REQUEST = 500 # Blogger's limit
# --- End Configuration ---

if BLOG_URL == "YOUR_BLOG_URL_HERE":
    print("Error: Please replace 'YOUR_BLOG_URL_HERE' with your actual blog URL in the script.")
    exit()

all_posts_data = []
start_index = 1
total_posts = None # We'll get this from the first request

print(f"Starting fetch for blog: {BLOG_URL}")

while True:
    feed_url = f"https://{BLOG_URL}/feeds/posts/default?alt=json&max-results={MAX_RESULTS_PER_REQUEST}&start-index={start_index}"
    print(f"Fetching: {feed_url}")

    try:
        response = requests.get(feed_url)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        if 'feed' not in data or 'entry' not in data['feed']:
            print("Feed format seems incorrect or no entries found.")
            if start_index == 1: # If error on first request, stop
                 print("Could not fetch initial feed. Check BLOG_URL.")
                 exit()
            else: # If error on subsequent request, might just be the end
                 break

        entries = data['feed']['entry']

        # Get total posts count from the first request
        if total_posts is None:
            if 'openSearch$totalResults' in data['feed'] and '$t' in data['feed']['openSearch$totalResults']:
                 total_posts = int(data['feed']['openSearch$totalResults']['$t'])
                 print(f"Total posts reported by feed: {total_posts}")
            else:
                 print("Warning: Could not determine total number of posts from feed.")
                 # Make a guess based on this batch to continue, might fetch extra
                 total_posts = start_index + len(entries) -1 + MAX_RESULTS_PER_REQUEST

        if not entries:
            print("No more entries found.")
            break # Exit loop if no entries are returned

        for entry in entries:
            post_url = None
            for link in entry.get('link', []):
                if link.get('rel') == 'alternate':
                    post_url = link.get('href')
                    break

            title = entry.get('title', {}).get('$t', 'Untitled')
            labels = [cat.get('term') for cat in entry.get('category', []) if cat.get('term')]

            if post_url:
                all_posts_data.append({
                    "url": post_url,
                    "title": title,
                    "labels": labels
                })

        print(f"Fetched {len(entries)} posts. Total collected so far: {len(all_posts_data)}")

        # Check if we've fetched enough based on total_posts (if known)
        if total_posts is not None and len(all_posts_data) >= total_posts:
             print("Collected posts count reached or exceeded total reported posts.")
             break

        # Prepare for the next iteration
        start_index += MAX_RESULTS_PER_REQUEST

        # Safety break if total_posts wasn't determined and we get an empty batch
        if total_posts is None and not entries:
             print("Stopping fetch as total posts unknown and received empty batch.")
             break

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        break
    except json.JSONDecodeError:
        print("Error decoding JSON response. Feed might be malformed.")
        break
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        break


# Write the data to the output file
try:
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_posts_data, f, indent=2, ensure_ascii=False)
    print(f"\nSuccessfully generated index file: {OUTPUT_FILE}")
    print(f"Total posts indexed: {len(all_posts_data)}")
    if total_posts is not None and len(all_posts_data) < total_posts:
         print(f"Warning: Indexed posts ({len(all_posts_data)}) is less than total reported ({total_posts}). Feed might be incomplete or have issues.")

except IOError as e:
    print(f"Error writing to file {OUTPUT_FILE}: {e}")
