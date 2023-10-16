# threadingwebdriver
Selenium headless webdriver using two threadpools.  
ThreadPool(1) for control browser.  
ThreadPool(custom_number) for read page(ex: get WebElement).  
Chrome only.  

## Initialize
```python
import threadingwebdriver
driver = threadingwebdriver.ChromeWebdriver()
driver.initialize()
```

## Close
Close driver. It will wait tasks of ThreadPools are finish.  
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
Concurrency
```python
import threadingwebdriver
driver = threadingwebdriver.ChromeWebdriver()
driver.initialize(read_thread_count = 3)
timeout = 2
url = "Input Your URL"
driver.open(timeout, url)

p_async = driver.get_element_xpath_async(timeout, '/html/body/div/p')
a_async = driver.get_element_xpath_async(timeout, '/html/body/div/a')
div_async = driver.get_element_xpath_async(timeout, '/html/body/div')

p = p_async.get()
a = a_async.get()
div = div_async.get()
```

## Get Element (Sync)
```python
timeout = 3
body_xpath = '/html/body'
body:WebElement = driver.get_element_xpath(timeout, body_xpath)
```

## Initialize Websocket Listener
```python
async def websocket_listener(listener):
    async for event in listener:
        payload_data = event.response.payload_data
        print(payload_data)

import threadingwebdriver
driver = threadingwebdriver.ChromeWebdriver()
driver.initialize(websocket_listening_function=websocket_listener)

url = 'https:// Input Your URL'
driver.open(3, url)
```

## Exceptions
Based on thread order.  
```python
url1 = 'https://www.google.com/'
url2 = 'https://www.github.com/'
driver.open_async(url1)
driver.open_async(url2)
timeout = 3
body_xpath = '/html/body'
body_xpath_result:WebElementAsyncResult = driver.get_element_xpath_async(timeout, body_xpath) 
# Exception: if run 'get_element_xpath_async()' before run 'open_async(url2)'.
```

```python
url1 = 'https://www.google.com/'
url2 = 'https://www.github.com/'
driver.open_async(url1)
timeout = 3
body_xpath = '/html/body'
body_xpath_result:WebElementAsyncResult = driver.get_element_xpath_async(timeout, body_xpath)
driver.open_async(url2) 
# Exception: run 'open_async(url2)' if not finish 'get_element_xpath_async()'.
```