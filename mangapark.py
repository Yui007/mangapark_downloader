# This script will download manga chapters from mangapark.net using Selenium
import time
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import io
import threading
import concurrent.futures
import zipfile
import shutil
import img2pdf

def get_chapter_info(manga_url, use_nsfw_mode=False):
    """Scrapes the manga page for chapter titles and URLs."""
    print(f"Fetching chapter information from: {manga_url}")

    if use_nsfw_mode:
        print("Using NSFW mode (Selenium)...")
        driver = None
        try:
            # Initialize browser with NSFW settings enabled
            driver = initialize_browser_with_nsfw()

            # Navigate to the manga page
            driver.get(manga_url)

            # Wait for the page to load and JavaScript to execute
            print("Waiting for page to load...")
            time.sleep(8)  # Give time for JavaScript to load chapters

            # Try to find chapter elements with multiple selectors
            chapter_elements = []

            # Primary selector based on the HTML structure
            chapter_elements = driver.find_elements(By.CSS_SELECTOR, 'a.link-hover.link-primary.visited\\:text-accent')

            if not chapter_elements:
                # Fallback selectors
                selectors_to_try = [
                    'a[href*="/title/"][href*="/chapter"]',
                    'a[href*="/c"]',
                    '.chapter-list a',
                    '[data-mal-sync-episode] a',
                    'a[href*="chapter"]'
                ]

                for selector in selectors_to_try:
                    chapter_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if chapter_elements:
                        print(f"Found chapters using selector: {selector}")
                        break

            if not chapter_elements:
                print("No chapter elements found. Saving page source for debugging...")
                # Save the page source for debugging
                debug_file = os.path.join("downloads", "debug_page_selenium.html")
                os.makedirs("downloads", exist_ok=True)
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print(f"Debug page saved to: {debug_file}")
                return None

            print(f"Found {len(chapter_elements)} potential chapters")

            chapters = []
            for element in chapter_elements:
                try:
                    title = element.text.strip()
                    href = element.get_attribute('href')

                    # Skip if title is empty or too short
                    if not title or len(title) < 3:
                        continue

                    # Skip if href is empty or not a chapter link
                    if not href or ('/title/' not in href and '/c' not in href):
                        continue

                    # Construct absolute URL
                    if href.startswith('http'):
                        url = href
                    else:
                        url = urljoin(manga_url, href)

                    chapters.append({'title': title, 'url': url})

                except Exception as e:
                    print(f"Error processing chapter element: {e}")
                    continue

            # Remove duplicates based on URL
            seen_urls = set()
            unique_chapters = []
            for chapter in chapters:
                if chapter['url'] not in seen_urls:
                    seen_urls.add(chapter['url'])
                    unique_chapters.append(chapter)

            chapters = unique_chapters

            # Reverse the chapters list so chapter 1 is at index 0
            chapters.reverse()

            print(f"Found {len(chapters)} unique chapters")
            return chapters

        except Exception as e:
            print(f"Error in Selenium processing: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    else:
        print("Using SFW mode (requests + BeautifulSoup)...")
        return get_chapter_info_sfw(manga_url)

def get_chapter_info_sfw(manga_url):
    """Scrapes the manga page for chapter titles and URLs using requests + BeautifulSoup (SFW mode)."""
    print(f"Fetching chapter information from: {manga_url}")
    try:
        response = requests.get(manga_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')

        chapters = []
        chapter_elements = soup.select('a.link-hover.link-primary.visited\\:text-accent')

        if not chapter_elements:
            print("No chapter elements found. Saving page for debugging...")
            # Save the page for debugging
            debug_file = os.path.join("downloads", "debug_page_sfw.html")
            os.makedirs("downloads", exist_ok=True)
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            print(f"Debug page saved to: {debug_file}")
            return None

        print(f"Found {len(chapter_elements)} potential chapters")

        for chapter_element in chapter_elements:
            title = chapter_element.get_text(strip=True)
            href = chapter_element['href']

            # Construct absolute URL - handle both relative and absolute URLs
            if href.startswith('http'):
                url = href
            else:
                url = urljoin(manga_url, href)

            chapters.append({'title': title, 'url': url})

        # Remove duplicates based on URL
        seen_urls = set()
        unique_chapters = []
        for chapter in chapters:
            if chapter['url'] not in seen_urls:
                seen_urls.add(chapter['url'])
                unique_chapters.append(chapter)

        chapters = unique_chapters

        # Reverse the chapters list so chapter 1 is at index 0
        chapters.reverse()

        print(f"Found {len(chapters)} unique chapters")
        return chapters

    except requests.exceptions.RequestException as e:
        print(f"Error fetching manga page: {e}")
        return None

def is_valid_manga_image(img_data, min_width=400, min_height=400, min_aspect_ratio=1.2):
    """
    Check if an image is a valid manga page (not an icon or small image).
    """
    try:
        img = Image.open(io.BytesIO(img_data))
        width, height = img.size
        
        # Calculate aspect ratio (always >= 1.0)
        aspect_ratio = max(width / height, height / width)
        
        # Calculate image size in KB
        img_size_kb = len(img_data) / 1024
        
        # Debug information
        print(f"Image dimensions: {width}x{height}, Aspect ratio: {aspect_ratio:.2f}, Size: {img_size_kb:.2f}KB")
        
        # Criteria for a valid manga page:
        # 1. Width and height both exceed minimums
        # 2. Aspect ratio exceeds minimum (manga pages are typically rectangular)
        # 3. File size is substantial (icons are typically small files)
        is_valid = (width > min_width and 
                   height > min_height and 
                   aspect_ratio >= min_aspect_ratio and
                   img_size_kb > 30)  # Most manga pages are at least 30KB
        
        if not is_valid:
            reasons = []
            if width <= min_width or height <= min_height:
                reasons.append(f"too small (minimum {min_width}x{min_height})")
            if aspect_ratio < min_aspect_ratio:
                reasons.append(f"too square-like (minimum aspect ratio {min_aspect_ratio})")
            if img_size_kb <= 30:
                reasons.append("file size too small")
            
            print(f"Image rejected: {', '.join(reasons)}")
        
        return is_valid
    except Exception as e:
        print(f"Error checking image dimensions: {e}")
        # If we can't check, assume it's not valid to be safe
        return False

def download_image(img_url, referer, img_index, chapter_dir, chapter_title):
    """
    Download a single image.
    Returns a tuple of (img_index, img_path, success) to maintain order.
    """
    try:
        print(f"[{chapter_title}] Downloading image {img_index+1}")
        
        # Download the image
        img_response = requests.get(img_url, headers={'Referer': referer})
        img_response.raise_for_status()
        
        # Check if this is a valid manga image (not an icon)
        if not is_valid_manga_image(img_response.content):
            print(f"[{chapter_title}] Skipping image {img_index+1} as it appears to be an icon or small image")
            return (img_index, None, False)
        
        # Save the image
        extension = img_url.split('.')[-1].split('?')[0].lower()  # Get file extension
        # Support multiple image formats
        if extension not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
            extension = 'jpg'  # Default to jpg if extension is not recognized
        
        img_path = os.path.join(chapter_dir, f"temp_{img_index:03d}.{extension}")
        with open(img_path, 'wb') as f:
            f.write(img_response.content)
            
        print(f"[{chapter_title}] Downloaded image {img_index+1}")
        return (img_index, img_path, True)
    except Exception as e:
        print(f"[{chapter_title}] Error downloading image {img_index+1}: {e}")
        return (img_index, None, False)

def enable_nsfw_settings(driver):
    """Enable NSFW settings in MangaPark - MUST be called before any manga operations."""
    try:
        print("Enabling NSFW settings...")
        driver.get("https://mangapark.net/site-settings?group=safeBrowsing")

        # Wait for the page to load
        time.sleep(3)

        # Find and click the NSFW radio button
        nsfw_radio = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="radio"][name="safe_reading"][value="2"]'))
        )

        # Click the NSFW option
        nsfw_radio.click()
        print("NSFW settings enabled successfully")

        # Wait a moment for the setting to be applied
        time.sleep(2)

        return True
    except Exception as e:
        print(f"Error enabling NSFW settings: {e}")
        return False

def initialize_browser_with_nsfw():
    """Initialize browser and enable NSFW settings globally."""
    print("Initializing browser with NSFW settings...")

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--non-headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")

    driver = webdriver.Chrome(options=chrome_options)

    # Enable NSFW settings first
    nsfw_enabled = enable_nsfw_settings(driver)
    if not nsfw_enabled:
        print("Warning: Could not enable NSFW settings, may not be able to access NSFW content")

    return driver

def download_chapter_with_selenium(chapter_url, chapter_title, max_concurrent_downloads=5):
    """Downloads images for a single chapter using Selenium."""
    print(f"Downloading chapter: {chapter_title}")

    # Create directory for the chapter
    chapter_dir = os.path.join("downloads", chapter_title.replace('/', '-').replace('\\', '-').replace(':', '-'))
    os.makedirs(chapter_dir, exist_ok=True)

    driver = None

    try:
        # Construct the absolute chapter URL
        base_url = "https://mangapark.net"
        absolute_chapter_url = urljoin(base_url, chapter_url)

        # Initialize browser with NSFW settings enabled
        driver = initialize_browser_with_nsfw()

        # Navigate to the chapter
        driver.get(absolute_chapter_url)

        # Wait for the page to load
        print(f"[{chapter_title}] Waiting for page to load...")
        time.sleep(5)  # Initial wait
        
        # Wait for images to load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img.w-full.h-full"))
            )
            print(f"[{chapter_title}] Images loaded successfully")
        except Exception as e:
            print(f"[{chapter_title}] Timeout waiting for images: {e}")
            # Continue anyway, some images might have loaded
        
        # Find all image elements
        image_elements = driver.find_elements(By.CSS_SELECTOR, "img.w-full.h-full")
        
        if not image_elements:
            # Try alternative selectors
            image_elements = driver.find_elements(By.CSS_SELECTOR, "main img")
        
        if not image_elements:
            print(f"[{chapter_title}] No images found. Saving page source for debugging...")
            with open(os.path.join(chapter_dir, "debug_page.html"), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            return chapter_dir, False
        
        print(f"[{chapter_title}] Found {len(image_elements)} images")
        
        # Get all image URLs first
        image_urls = []
        for img in image_elements:
            img_url = img.get_attribute('src')
            if img_url:
                image_urls.append(img_url)
        
        # Download images with controlled concurrency
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_downloads) as executor:
            # Submit all image downloads to the executor
            future_to_index = {
                executor.submit(download_image, img_url, absolute_chapter_url, i, chapter_dir, chapter_title): i
                for i, img_url in enumerate(image_urls)
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_index):
                result = future.result()  # (img_index, img_path, success)
                if result[2]:  # If successful
                    results.append(result)
        
        # Sort results by original image index to maintain order
        results.sort(key=lambda x: x[0])
        
        # Rename files to their final sequential names
        valid_images_count = 0
        valid_image_paths = []
        for _, temp_path, _ in results:
            if temp_path:
                valid_images_count += 1
                extension = os.path.splitext(temp_path)[1]
                final_path = os.path.join(chapter_dir, f"{valid_images_count:03d}{extension}")
                os.rename(temp_path, final_path)
                valid_image_paths.append(final_path)
        
        print(f"[{chapter_title}] Chapter downloaded successfully with {valid_images_count} valid images")
        return chapter_dir, valid_images_count > 0
        
    except Exception as e:
        print(f"[{chapter_title}] Error in Selenium processing: {e}")
        return chapter_dir, False
    finally:
        if driver:
            driver.quit()

def create_cbz(chapter_dir, chapter_title):
    """Create a CBZ file from downloaded images."""
    try:
        # Get all image files in the directory
        image_files = []
        for file in os.listdir(chapter_dir):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                image_files.append(os.path.join(chapter_dir, file))
        
        if not image_files:
            print(f"No images found in {chapter_dir} to create CBZ")
            return None
        
        # Sort files by name (which should be numerical order)
        image_files.sort()
        
        # Create CBZ file
        cbz_path = f"{chapter_dir}.cbz"
        with zipfile.ZipFile(cbz_path, 'w') as zipf:
            for img_file in image_files:
                # Add file to zip with just the filename, not the full path
                zipf.write(img_file, os.path.basename(img_file))
        
        print(f"Created CBZ file: {cbz_path}")
        return cbz_path
    except Exception as e:
        print(f"Error creating CBZ file: {e}")
        return None

def create_pdf(chapter_dir, chapter_title):
    """Create a PDF file from downloaded images."""
    try:
        # Get all image files in the directory
        image_files = []
        for file in os.listdir(chapter_dir):
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):  # img2pdf doesn't support all formats
                image_files.append(os.path.join(chapter_dir, file))
        
        if not image_files:
            print(f"No images found in {chapter_dir} to create PDF")
            return None
        
        # Sort files by name (which should be numerical order)
        image_files.sort()
        
        # Create PDF file
        pdf_path = f"{chapter_dir}.pdf"
        with open(pdf_path, "wb") as f:
            pdf_bytes = img2pdf.convert(image_files)
            if pdf_bytes:
                f.write(pdf_bytes)
        
        print(f"Created PDF file: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"Error creating PDF file: {e}")
        return None

def download_chapters_threaded(chapters_to_download, max_concurrent_downloads=5):
    """
    Download multiple chapters using threading.
    
    Args:
        chapters_to_download: List of chapter dictionaries to download
        max_concurrent_downloads: Maximum number of concurrent downloads (applies to both chapters and images)
    """
    successful_downloads = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_downloads) as executor:
        # Submit all chapter downloads to the executor
        future_to_chapter = {
            executor.submit(download_chapter_with_selenium, chapter['url'], chapter['title'], max_concurrent_downloads): chapter['title']
            for chapter in chapters_to_download
        }
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_chapter):
            chapter_title = future_to_chapter[future]
            try:
                # Get the result (chapter directory and success status)
                chapter_dir, success = future.result()
                if success:
                    successful_downloads.append((chapter_dir, chapter_title))
                    print(f"Completed download of chapter: {chapter_title}")
                else:
                    print(f"Chapter download completed but may have issues: {chapter_title}")
            except Exception as e:
                print(f"Chapter download failed for {chapter_title}: {e}")
    
    return successful_downloads

def main():
    # Ask user for manga URL
    manga_url = input("Enter the URL of the manga on mangapark.net: ")

    # Ask user for NSFW mode
    nsfw_choice = input("Enable NSFW mode for adult content? (y/n): ").lower()
    use_nsfw_mode = nsfw_choice == 'y'

    # Get chapter information
    chapters = get_chapter_info(manga_url, use_nsfw_mode)
    
    if not chapters:
        print("No chapters found or error occurred.")
        return
        
    # Display available chapters
    print(f"Found {len(chapters)} chapters:")
    for i, chapter in enumerate(chapters):
        print(f"{i+1}. {chapter['title']}")
        
    # Ask user which chapters to download
    selection = input("Enter chapter number to download (single) or a range (e.g., 5-10), or 'all' for all chapters: ")
    
    # Create downloads directory if it doesn't exist
    os.makedirs("downloads", exist_ok=True)
    
    # Process user selection
    chapters_to_download = []
    
    if selection.lower() == 'all':
        chapters_to_download = chapters
    elif '-' in selection:
        # Range of chapters
        try:
            start, end = map(int, selection.split('-'))
            if start > 0 and end <= len(chapters):
                chapters_to_download = chapters[start-1:end]
            else:
                print("Invalid chapter range.")
                return
        except ValueError:
            print("Invalid range format.")
            return
    else:
        # Single chapter
        try:
            index = int(selection) - 1
            if 0 <= index < len(chapters):
                chapters_to_download = [chapters[index]]
            else:
                print("Chapter number out of range.")
                return
        except ValueError:
            print("Invalid chapter number.")
            return
            
    if not chapters_to_download:
        print("No valid chapters selected.")
        return
    
    # Ask for threading options
    use_threading = input("Use multi-threading for faster downloads? (y/n): ").lower() == 'y'
    
    successful_downloads = []
    
    if use_threading:
        try:
            max_concurrent_downloads = int(input("Enter maximum number of concurrent downloads (recommended: 3-8): "))
            if max_concurrent_downloads < 1:
                max_concurrent_downloads = 5  # Default to 5 if invalid input
        except ValueError:
            max_concurrent_downloads = 5  # Default to 5 if invalid input
            
        print(f"Initiating download for {len(chapters_to_download)} chapter(s) with {max_concurrent_downloads} concurrent downloads...")
        successful_downloads = download_chapters_threaded(chapters_to_download, max_concurrent_downloads)
    else:
        print(f"Initiating download for {len(chapters_to_download)} chapter(s)...")
        # Download selected chapters sequentially
        for chapter in chapters_to_download:
            chapter_dir, success = download_chapter_with_selenium(chapter['url'], chapter['title'], 1)  # Use 1 for sequential downloads
            if success:
                successful_downloads.append((chapter_dir, chapter['title']))
            time.sleep(2)  # Add delay between chapter downloads
    
    # Ask user if they want to convert to CBZ/PDF
    if successful_downloads:
        convert_option = input("Convert downloaded chapters to CBZ or PDF? (cbz/pdf/both/none): ").lower()
        
        if convert_option in ['cbz', 'both']:
            print("Converting chapters to CBZ format...")
            for chapter_dir, chapter_title in successful_downloads:
                cbz_path = create_cbz(chapter_dir, chapter_title)
                if cbz_path:
                    delete_option = input(f"CBZ created for {chapter_title}. Delete original images? (y/n): ").lower()
                    if delete_option == 'y':
                        try:
                            shutil.rmtree(chapter_dir)
                            print(f"Deleted original images for {chapter_title}")
                        except Exception as e:
                            print(f"Error deleting directory {chapter_dir}: {e}")
        
        if convert_option in ['pdf', 'both']:
            print("Converting chapters to PDF format...")
            for chapter_dir, chapter_title in successful_downloads:
                # Check if directory still exists (might have been deleted after CBZ creation)
                if os.path.exists(chapter_dir):
                    pdf_path = create_pdf(chapter_dir, chapter_title)
                    if pdf_path and convert_option != 'both':  # If 'both', we already asked about deletion
                        delete_option = input(f"PDF created for {chapter_title}. Delete original images? (y/n): ").lower()
                        if delete_option == 'y':
                            try:
                                shutil.rmtree(chapter_dir)
                                print(f"Deleted original images for {chapter_title}")
                            except Exception as e:
                                print(f"Error deleting directory {chapter_dir}: {e}")
    
    print("Download complete.")

if __name__ == "__main__":
    main()
