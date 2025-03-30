import requests
import json
import math
import time
import re # Import regex for finding images in content
import os # Import os for checking file existence

# --- Configuration ---
BLOG_URL = "kfangirl4life.blogspot.com" # Your specific blog URL
OUTPUT_FILE = "blog_index.json"
PRIORITY_LABELS_FILE = "priority_labels.txt" # File to read priority labels from
MAX_RESULTS_PER_REQUEST = 500 # Blogger's limit
REQUEST_DELAY_SECONDS = 0.5 # Optional delay between requests
DEFAULT_IMAGE = "https://resources.blogblog.com/img/blank.gif" # Default blank image
# --- End Configuration ---

# --- Load Priority Labels ---
priority_labels_lower = set() # Use a set for efficient lookup, store lowercase
if os.path.exists(PRIORITY_LABELS_FILE):
    try:
        with open(PRIORITY_LABELS_FILE, 'r', encoding='utf-8') as f:
            # Read lines, strip whitespace, convert to lowercase, ignore empty lines
            priority_labels_lower = {line.strip().lower() for line in f if line.strip()}
        if priority_labels_lower:
             print(f"Loaded priority labels (case-insensitive): {', '.join(priority_labels_lower)}")
        else:
             print(f"{PRIORITY_LABELS_FILE} exists but is empty or contains no valid labels.")
    except IOError as e:
        print(f"Warning: Could not read {PRIORITY_LABELS_FILE}: {e}. Proceeding without label prioritization.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred reading {PRIORITY_LABELS_FILE}: {e}. Proceeding without label prioritization.")
else:
    print(f"Optional file {PRIORITY_LABELS_FILE} not found. Proceeding without label prioritization.")
# --- End Load Priority Labels ---


# Check if the URL looks like the placeholder - it shouldn't if set correctly above
if BLOG_URL == "YOUR_BLOG_URL_HERE":
    print("Error: BLOG_URL appears to be the placeholder. Please edit the script.")
    exit()

# Helper function to extract the first image URL from HTML content
def find_first_image_in_content(html_content):
    if not html_content:
        return None
    match = re.search(r'<img[^>]+src=(["\'])(.*?)\1', html_content, re.IGNORECASE)
    if match:
        return match.group(2)
    return None

# Helper function to reorder labels based on priority
def prioritize_labels(original_labels):
    if not priority_labels_lower or not original_labels:
        return original_labels # Return original if no priority set or no labels

    prioritized = []
    remaining = []
    found_priority = None

    # Iterate through original labels to find the *first* priority match
    for label in original_labels:
        if label.lower() in priority_labels_lower and found_priority is None:
            found_priority = label # Store the first priority label found (preserving case)
        else:
            remaining.append(label) # Add non-priority or subsequent labels to remaining

    # If a priority label was found, put it first, followed by the rest
    if found_priority:
        return [found_priority] + remaining
    else:
        # If no priority label found, return the original order
        return original_labels

all_posts_data = []
start_index = 1
total_posts = None

print(f"Starting fetch for blog: {BLOG_URL}")

while True:
    feed_url = f"https://{BLOG_URL}/feeds/posts/default?alt=json&max-results={MAX_RESULTS_PER_REQUEST}&start-index={start_index}"
    print(f"Fetching: {feed_url}")

    try:
        response = requests.get(feed_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'feed' not in data or 'entry' not in data.get('feed', {}):
            if 'feed' in data and not data['feed'].get('entry'):
                 print("No more entries found in this batch.")
                 if total_posts is not None and len(all_posts_data) < total_posts:
                      print(f"Warning: Reached end of feed entries but collected posts ({len(all_posts_data)}) is less than total reported ({total_posts}).")
                 break
            else:
                 print("Feed format seems incorrect or 'entry' field is missing.")
                 if start_index == 1:
                      print("Could not fetch initial feed. Check BLOG_URL and feed validity.")
                      exit()
                 else:
                      print("Stopping fetch due to unexpected feed format on subsequent request.")
                      break

        entries = data['feed']['entry']

        if total_posts is None:
            if 'openSearch$totalResults' in data['feed'] and '$t' in data['feed']['openSearch$totalResults']:
                 try:
                      total_posts = int(data['feed']['openSearch$totalResults']['$t'])
                      print(f"Total posts reported by feed: {total_posts}")
                 except (ValueError, TypeError):
                      print("Warning: Could not parse total number of posts from feed.")
                      total_posts = -1
            else:
                 print("Warning: Could not determine total number of posts from feed.")
                 total_posts = -1

        for entry in entries:
            post_url = None
            for link in entry.get('link', []):
                if link.get('rel') == 'alternate' and link.get('type') == 'text/html':
                    post_url = link.get('href')
                    break
            if not post_url:
                 for link in entry.get('link', []):
                      if link.get('rel') == 'alternate':
                           post_url = link.get('href')
                           break

            title = entry.get('title', {}).get('$t', 'Untitled')
            original_labels = [cat.get('term') for cat in entry.get('category', []) if cat.get('term')]
            # --- Prioritize Labels ---
            final_labels = prioritize_labels(original_labels)
            # --- End Prioritize Labels ---
            raw_date = entry.get('published', {}).get('$t', None)

            image_url = None
            if 'media$thumbnail' in entry and 'url' in entry['media$thumbnail']:
                image_url = entry['media$thumbnail']['url']
            if not image_url:
                 content = entry.get('content', {}).get('$t', '')
                 image_url = find_first_image_in_content(content)
            if not image_url:
                 image_url = DEFAULT_IMAGE

            if post_url:
                all_posts_data.append({
                    "url": post_url,
                    "title": title,
                    "labels": final_labels, # Save the potentially reordered labels
                    "date": raw_date,
                    "image": image_url
                })
            else:
                 print(f"Warning: Could not find 'alternate' URL for entry with title: {title}")

        print(f"Fetched {len(entries)} posts in this batch. Total collected so far: {len(all_posts_data)}")

        if total_posts is not None and total_posts > 0 and len(all_posts_data) >= total_posts:
             print("Collected posts count reached or exceeded total reported posts.")
             break
        if len(entries) < MAX_RESULTS_PER_REQUEST:
             print("Fetched less than max results, assuming end of feed.")
             break

        start_index += MAX_RESULTS_PER_REQUEST
        if REQUEST_DELAY_SECONDS > 0:
             print(f"Waiting {REQUEST_DELAY_SECONDS} seconds before next request...")
             time.sleep(REQUEST_DELAY_SECONDS)

    except requests.exceptions.Timeout:
        print(f"Error: Request timed out while fetching {feed_url}")
        break
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP Error {e.response.status_code} for URL: {feed_url}")
        break
    except requests.exceptions.RequestException as e:
        print(f"Error: Network or request error: {e}")
        break
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from {feed_url}.")
        break
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        break

if all_posts_data:
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_posts_data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully generated index file: {OUTPUT_FILE}")
        print(f"Total posts indexed: {len(all_posts_data)}")
        if total_posts is not None and total_posts > 0 and len(all_posts_data) < total_posts:
             print(f"Warning: Indexed posts ({len(all_posts_data)}) is less than total reported ({total_posts}).")
        elif total_posts == -1:
             print("Note: Total post count could not be determined from feed.")
    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")
else:
     print("\nNo post data was collected. Index file was not written.")
