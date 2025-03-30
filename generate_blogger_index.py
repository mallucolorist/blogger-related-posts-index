import requests
import json
import math
import time
import re # Import regex for finding images in content

# --- Configuration ---
BLOG_URL = "kfangirl4life.blogspot.com" # Your specific blog URL
OUTPUT_FILE = "blog_index.json"
MAX_RESULTS_PER_REQUEST = 500 # Blogger's limit
REQUEST_DELAY_SECONDS = 0.5 # Optional delay between requests
DEFAULT_IMAGE = "https://resources.blogblog.com/img/blank.gif" # Default blank image
# --- End Configuration ---

# Check if the URL looks like the placeholder - it shouldn't if set correctly above
if BLOG_URL == "YOUR_BLOG_URL_HERE":
    print("Error: BLOG_URL appears to be the placeholder. Please edit the script.")
    exit()

# Helper function to extract the first image URL from HTML content
def find_first_image_in_content(html_content):
    if not html_content:
        return None
    # Regex to find the src attribute of the first img tag
    match = re.search(r'<img[^>]+src=(["\'])(.*?)\1', html_content, re.IGNORECASE)
    if match:
        return match.group(2) # Return the URL found in the src attribute
    return None

all_posts_data = []
start_index = 1
total_posts = None # We'll get this from the first request

print(f"Starting fetch for blog: {BLOG_URL}")

while True:
    # Construct the feed URL using the BLOG_URL variable
    feed_url = f"https://{BLOG_URL}/feeds/posts/default?alt=json&max-results={MAX_RESULTS_PER_REQUEST}&start-index={start_index}"
    print(f"Fetching: {feed_url}")

    try:
        response = requests.get(feed_url, timeout=30) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        # Basic validation of the received data structure
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

        # Get total posts count from the first request
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


        # Process the entries if any exist in this batch
        for entry in entries:
            post_url = None
            # Find the 'alternate' link which is the actual post URL
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
            # Extract labels, ensuring 'term' exists
            labels = [cat.get('term') for cat in entry.get('category', []) if cat.get('term')]
            # Extract raw publication date
            raw_date = entry.get('published', {}).get('$t', None)

            # --- Extract Image URL ---
            image_url = None
            # 1. Try media$thumbnail
            if 'media$thumbnail' in entry and 'url' in entry['media$thumbnail']:
                image_url = entry['media$thumbnail']['url']
            # 2. If no thumbnail, try finding first image in content
            if not image_url:
                 content = entry.get('content', {}).get('$t', '')
                 image_url = find_first_image_in_content(content)
            # 3. If still no image, use default
            if not image_url:
                 image_url = DEFAULT_IMAGE
            # --- End Image URL Extraction ---


            if post_url:
                all_posts_data.append({
                    "url": post_url,
                    "title": title,
                    "labels": labels,
                    "date": raw_date, # Add raw date
                    "image": image_url # Add image url
                })
            else:
                 print(f"Warning: Could not find 'alternate' URL for entry with title: {title}")


        print(f"Fetched {len(entries)} posts in this batch. Total collected so far: {len(all_posts_data)}")

        # Check if we've fetched enough based on total_posts (if known and valid)
        if total_posts is not None and total_posts > 0 and len(all_posts_data) >= total_posts:
             print("Collected posts count reached or exceeded total reported posts.")
             break

        # If the number of entries fetched is less than requested, assume it's the last page
        if len(entries) < MAX_RESULTS_PER_REQUEST:
             print("Fetched less than max results, assuming end of feed.")
             break

        # Prepare for the next iteration
        start_index += MAX_RESULTS_PER_REQUEST

        # Optional delay between requests
        if REQUEST_DELAY_SECONDS > 0:
             print(f"Waiting {REQUEST_DELAY_SECONDS} seconds before next request...")
             time.sleep(REQUEST_DELAY_SECONDS)


    except requests.exceptions.Timeout:
        print(f"Error: Request timed out while fetching {feed_url}")
        print("Check network connection or increase timeout value.")
        break
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP Error {e.response.status_code} for URL: {feed_url}")
        if e.response.status_code == 404:
             print("Blog URL might be incorrect or feed path is wrong.")
        elif e.response.status_code == 403:
             print("Access forbidden. Blog might be private or require authentication.")
        break
    except requests.exceptions.RequestException as e:
        print(f"Error: Network or request error: {e}")
        break
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from {feed_url}. Feed might be malformed or response was not JSON.")
        break
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        break


# Write the collected data to the output file
if all_posts_data: # Only write if we collected some data
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_posts_data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully generated index file: {OUTPUT_FILE}")
        print(f"Total posts indexed: {len(all_posts_data)}")
        if total_posts is not None and total_posts > 0 and len(all_posts_data) < total_posts:
             print(f"Warning: Indexed posts ({len(all_posts_data)}) is less than total reported ({total_posts}). Feed might be incomplete or have issues.")
        elif total_posts == -1:
             print("Note: Total post count could not be determined from feed.")

    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE}: {e}")
else:
     print("\nNo post data was collected. Index file was not written.")
