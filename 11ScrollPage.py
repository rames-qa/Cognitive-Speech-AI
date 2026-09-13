from selenium import webdriver
driver = webdriver.Chrome()
driver.get("https://www.amazon.in")
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
driver.quit()