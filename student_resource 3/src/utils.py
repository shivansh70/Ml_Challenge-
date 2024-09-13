import re
import constants
import os
import requests
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


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  

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

def create_placeholder_image(image_save_path):
    try:
        placeholder_image = Image.new('RGB', (100, 100), color='black')
        placeholder_image.save(image_save_path)
    except Exception as e:
        return

def download_image(image_link, save_folder, retries=3, delay=3):
    
    if not isinstance(image_link, str):
        return

    filename = Path(image_link).name
    image_save_path = os.path.join(save_folder, filename)

    if os.path.exists(image_save_path):
        return image_save_path

    for _ in range(retries):
        try:
            urllib.request.urlretrieve(image_link, image_save_path)
            return image_save_path
        except:
            time.sleep(delay)

    create_placeholder_image(image_save_path)  # Create a black placeholder image for invalid links/images
    return image_save_path

def download_images(image_links, download_folder, allow_multiprocessing=True):
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    if allow_multiprocessing:
        download_image_partial = partial(
            download_image, save_folder=download_folder, retries=3, delay=3)

        with multiprocessing.Pool(60) as pool:
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

def process_images_with_easyocr(download_folder):
    ocr_results = {}
    image_paths = [str(file) for file in Path(download_folder).glob('*') if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']]
    
    # Initialize EasyOCR Reader
    reader = easyocr.Reader(['en'])

    for image_path in image_paths:
        # Perform OCR using EasyOCR
        results = reader.readtext(image_path)
        
        # Extract text from results
        text = ' '.join([result[1] for result in results])
        
        # Store the text with image name as key
        ocr_results[Path(image_path).stem] = text 
    
    return ocr_results