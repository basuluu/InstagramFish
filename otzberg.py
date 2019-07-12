import requests
from bs4 import BeautifulSoup
import re


def get_user_id(user_link):
    url = 'https://www.otzberg.net/iguserid/index.php'
    try:
        if 'instagram.com' in user_link:
            payload = {'url': user_link}
            r = requests.post(url, data=payload)
            info = BeautifulSoup(r.text).findAll(
                'div', {'class': 'hero-unit'})[0].get_text()
        else:
            payload = {'username': user_link}
            r = requests.post(url, data=payload)
            info = BeautifulSoup(r.text).findAll('p')[0].get_text()
        user_id = re.search('\d+', info).group()
        return user_id
    except:
        return 0
