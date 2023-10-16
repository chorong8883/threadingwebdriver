# threadingwebdriver
Selenium webdriver using two threadpools. (Available chrome only now.)  
ThreadPool(1) for control browser.  
ThreadPool(custom_number) for read page(get WebElement).  

## Initialize
```python
import threadingwebdriver
driver = threadingwebdriver.ChromeWebdriver()
driver.initialize()
```

## Close
Close driver. Wait tasks of ThreadPools are finish.  
```python
driver.close()
```

## Open URL (Async)
```python
url = 'https://www.google.com/'
driver.open_async(url)
```

## Open URL (Sync)
```python
url = 'https://www.google.com/'
is_open:bool = driver.open(3, url)
```

## Get Element (Async)
```python
url = 'https://www.google.com/'
driver.open_async(url)

timeout = 3
body_xpath = '/html/body'
body_xpath_result:WebElementAsyncResult = driver.get_element_xpath_async(timeout, body_xpath)
# code...
body:WebElement = body_xpath_result.get()
```

## Get Element (Sync)
```python
timeout = 3
body_xpath = '/html/body'
body:WebElement = driver.get_element_xpath(timeout, body_xpath)
```

## Exceptions
Based on thread priority.  
```python
url1 = 'https://www.google.com/'
url2 = 'https://www.github.com/'
driver.open_async(url1)
driver.open_async(url2)
timeout = 3
body_xpath = '/html/body'
body_xpath_result:WebElementAsyncResult = driver.get_element_xpath_async(timeout, body_xpath) 
# Exception: if run before open url2.
```

```python
url1 = 'https://www.google.com/'
url2 = 'https://www.github.com/'
driver.open_async(url1)
timeout = 3
body_xpath = '/html/body'
body_xpath_result:WebElementAsyncResult = driver.get_element_xpath_async(timeout, body_xpath)
driver.open_async(url2) # Exception: Open url2 before get element from url1.
```