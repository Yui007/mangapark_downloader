# MangaPark Downloader

A Python script to download manga chapters from [mangapark.net](https://mangapark.net) using Selenium and convert them into CBZ or PDF formats.

## Features

- Fetches manga chapter list from MangaPark
- Downloads manga chapter images using headless Chrome
- Filters out icons/small images to avoid junk
- Multi-threaded downloading for faster performance
- Converts downloaded chapters to:
  - CBZ (Comic Book Zip)
  - PDF (if image format supported)
- Interactive CLI

## Requirements

- Python 3.7+
- Google Chrome
- ChromeDriver (matching your Chrome version)

## Python Dependencies

Install the dependencies using pip:

```bash
pip install -r requirements.txt
```

requests
beautifulsoup4
selenium
Pillow
img2pdf

## Usage
Clone the repository or download the script:

```bash
git clone https://github.com/Yui007/mangapark_downloader
cd mangapark_downloader
```

Run the script:

```bash
python mangapark.py
```

Enter the manga URL from https://mangapark.net when prompted.

Select the chapter(s) to download:

Single: 5

Range: 5-10

All: all

Choose whether to use multi-threading.

Choose conversion output: CBZ, PDF, both, or none.

## Notes
Downloaded files will be saved in the downloads/ directory.

CBZ and PDF files will be saved in the same location as the chapter folder.

Chrome must be installed and the correct chromedriver must be accessible in your system path.

## Example
```text
Enter the URL of the manga on mangapark.net: https://mangapark.net/title/abc123
Enter chapter number to download (single) or a range (e.g., 5-10), or 'all' for all chapters: 1-3
Use multi-threading for faster downloads? (y/n): y
Enter maximum number of concurrent downloads (recommended: 3-8): 5
Convert downloaded chapters to CBZ or PDF? (cbz/pdf/both/none): both
```

## License
This project is licensed under the MIT License.
