import re
import constants
import os
import urllib.request
import pandas as pd
import multiprocessing
import time
from time import time as timer
from tqdm import tqdm
import numpy as np
from pathlib import Path
from functools import partial
from PIL import Image
import pytesseract


########
import easyocr

########
from PIL import Image
from io import BytesIO
import urllib.request
import logging
from urllib.error import URLError, HTTPError
import requests
from pathlib import Path

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  

ALLOWED_UNITS = {'cubic inch', 'microlitre', 'milligram', 'decilitre', 'gallon', 'volt', 'litre', 'imperial gallon', 'watt', 'fluid ounce', 'gram', 'ton', 'millilitre', 'centimetre', 'kilogram', 'microgram', 'centilitre', 'yard', 'foot', 'cup', 'kilowatt', 'pound', 'kilovolt', 'ounce', 'cubic foot', 'millivolt', 'metre', 'inch', 'pint', 'millimetre', 'quart'}

def common_mistake(unit):
    if unit in constants.allowed_units:
        return unit
    if unit.replace('ter', 'tre') in constants.allowed_units:
        return unit.replace('ter', 'tre')
    if unit.replace('feet', 'foot') in constants.allowed_units:
        return unit.replace('feet', 'foot')
    return unit

def parse_string(s):
    s_stripped = "" if s == None or str(s) == 'nan' else s.strip()
    if s_stripped == "":
        return None, None
    pattern = re.compile(r'^-?\d+(\.\d+)?\s+[a-zA-Z\s]+$')
    if not pattern.match(s_stripped):
        raise ValueError("Invalid format in {}".format(s))
    parts = s_stripped.split(maxsplit=1)
    number = float(parts[0])
    unit = common_mistake(parts[1])
    if unit not in constants.allowed_units:
        raise ValueError("Invalid unit [{}] found in {}. Allowed units: {}".format(
            unit, s, constants.allowed_units))
    return number, unit

# Creating placeholder image
def create_placeholder_image(image_save_path):
    """Create a placeholder image if download fails."""
    try:
        placeholder_image = Image.new('RGB', (100, 100), color='black')
        placeholder_image.save(image_save_path, 'JPEG')
    except Exception as e:
        logging.error(f"Failed to create placeholder image {image_save_path}: {e}")

# Function to download the image
def download_image(image_link, save_folder, retries=3, delay=3):
    """Download an image from the link and save it locally."""
    if not isinstance(image_link, str):
        logging.error(f"Invalid image link: {image_link}")
        return None

    filename = Path(image_link).name
    image_save_path = os.path.join(save_folder, filename)

    # Attempt to download and overwrite existing images
    for attempt in range(retries):
        try:
            logging.info(f"Attempting to download {image_link}, Attempt {attempt + 1}")
            response = requests.get(image_link, stream=True)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image = image.convert('RGB')  # Ensure image is in RGB format
                image.save(image_save_path, 'JPEG')  # Save image as JPEG
                logging.info(f"Successfully downloaded image: {image_save_path}")
                return image_save_path
            else:
                logging.error(f"Failed to download {image_link}, HTTP Status: {response.status_code}")
                time.sleep(delay)

        except Exception as e:
            logging.error(f"Failed to download {image_link}, Error: {e}")
            time.sleep(delay)

    # Create a placeholder image if download fails
    logging.warning(f"Failed to download image after {retries} retries, creating placeholder: {image_save_path}")
    create_placeholder_image(image_save_path)
    return image_save_path

def download_images(image_links, download_folder, allow_multiprocessing=True):
    """Download images with optional multiprocessing."""
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    num_processes = min(10, multiprocessing.cpu_count())  # Limit to 10 or the number of available CPUs

    if allow_multiprocessing:
        download_image_partial = partial(download_image, save_folder=download_folder, retries=3, delay=3)

        with multiprocessing.Pool(num_processes) as pool:
            image_paths = list(tqdm(pool.imap(download_image_partial, image_links), total=len(image_links)))
            pool.close()
            pool.join()
            return image_paths
    else:
        image_paths = []
        for image_link in tqdm(image_links, total=len(image_links)):
            image_path = download_image(image_link, save_folder=download_folder, retries=3, delay=3)
            image_paths.append(image_path)
        return image_paths


# Add the OCR functionality
def extract_text_from_image(image_path):
    """
    Applies OCR to extract text from a given image.
    """
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Failed to extract text from image {image_path}: {e}")
        return ""

def process_images_with_ocr(image_links, download_folder):
    """
    Downloads images and applies OCR to extract text.
    """
    image_paths = download_images(image_links, download_folder)
    
    ocr_results = {}
    
    for image_path in image_paths:
        text = extract_text_from_image(image_path)
        ocr_results[Path(image_path).stem] = text 
    
    return ocr_results



def process_images_with_ocr_justin(download_folder):
    ocr_results = {}
    image_paths = [str(file) for file in Path(download_folder).glob('*') if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']]

    
    for image_path in image_paths:
        text = extract_text_from_image(image_path)
        ocr_results[Path(image_path).stem] = text 
    
    return ocr_results

def extract_quantitative_data(text):
    # Define a regex pattern to match numbers and units
    pattern = r'\b(\d+(\.\d+)?)\s*(' + '|'.join(re.escape(unit) for unit in ALLOWED_UNITS) + r')\b'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    # Format matches as a dictionary
    quantitative_data = {match[2].lower(): match[0] for match in matches}
    return quantitative_data

def process_images_with_easyocr(images_path):
    import easyocr
    import os

    reader = easyocr.Reader(['en'])
    results = {}

    for image_name in os.listdir(images_path):
        image_path = os.path.join(images_path, image_name)
        result = reader.readtext(image_path)
        text = ' '.join([res[1] for res in result])
        
        # Extract quantitative data
        quantitative_data = extract_quantitative_data(text)
        results[image_name] = quantitative_data

    return results