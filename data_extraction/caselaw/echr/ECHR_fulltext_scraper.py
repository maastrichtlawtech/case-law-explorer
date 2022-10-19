import os
import sys
import pandas as pd
import numpy as np

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import text_to_be_present_in_element
from selenium.webdriver.common.by import By

# From https://stackoverflow.com/questions/50578809/how-can-i-get-the-xpath-from-a-webelement.
def make_xpath(child_element, xpath):
    child_tag = child_element.tag_name
    if child_tag == "html":
        return ''.join(["/html[1]", xpath])
    parent_element = child_element.find_element(By.XPATH, "..")
    children_elements = parent_element.find_elements(By.XPATH, "*")
    count = 0
    for i in range(len(children_elements)):
        children_element = children_elements[i]
        children_element_tag = children_element.tag_name
        if child_tag == children_element_tag:
            count += 1
        if child_element == children_element:
            return make_xpath(parent_element, ''.join(['/', child_tag, '['+str(count)+']', xpath]))
    print("mission failed we'll get 'em next time")
    return

def display_all_elements(driver):
    elements = driver.find_elements(By.XPATH, "//*")
    for element in elements:
        print("element: ", element)
        print("text: ", element.text)
        print("value: ", element.get_attribute("value"))
        print("tag name: ", element.tag_name)
        print("xpath:", make_xpath(element, ""), "\n")
    driver.quit()

def get_full_text(driver, extractedappno, id):
    if extractedappno == "":
        print("document unavailable")
        return ""
    URL = "https://hudoc.echr.coe.int/eng#{%22itemid%22:[%22"+id+"%22]}"
    try:
        driver.get(URL)
        WebDriverWait(driver, 10).until(text_to_be_present_in_element((By.XPATH, 
                                                                       "/html[1]/body[1]"), 
                                                                       "PROCEDURE"
                                                                       ))
        full_text = driver.find_elements(By.XPATH, "/html[1]/body[1]")[0].text
        print(''.join(["full text for ", str(id), " aquired"]))
        return full_text
    except:
        print("timeout")
        return ""

dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
echr_metadata_dir = ''.join(['\\'.join(dir.replace('\\', '/').split('/')[:-2]), "\\data\\echr"])
cases = pd.read_csv(''.join([echr_metadata_dir, "\\echr_metadata.csv"]))[["ecli",
                                                                          "itemid",
                                                                          "extractedappno"
                                                                          ]]
cases["extractedappno"] = cases["extractedappno"].fillna("")
service = Service("C:\Chromium\chromedriver_win32\chromedriver.exe")
options = Options()
options.headless = True
driver = Chrome(service=service, options=options)
cases["fulltext"] = cases.apply(lambda row: get_full_text(driver, 
                                                          row["extractedappno"], 
                                                          row["itemid"]), 
                                                          axis=1
                                                          )
full_texts = cases[["ecli", "fulltext"]]
full_texts.to_csv(''.join([echr_metadata_dir, "\\fulltexts.csv"]))




