from InstagramAPI import InstagramAPI
from collections import deque
from logging.handlers import RotatingFileHandler
import logging
import settings
import time
import random
import datetime
import pickle
import os
import otzberg
import atexit
import sys
import traceback


class InstagramFish:

    def __init__(self):
        self.api = InstagramAPI(settings.username, settings.password)
        print(settings.username)

    def set_proxy(self):
        if settings.proxy:
            self.log("Использую proxy: {}".format(settings.proxy))
            proxies = {
                'https': settings.proxy
            }
            self.api.s.proxies.update(proxies)

    def authorize(self):
        return self.api.login()

    def get_user_id_list_otzberg(self, username_list):
        user_id_list = []
        for username in username_list:
            user_id = otzberg.get_user_id(username)
            if user_id:
                user_id_list.append(user_id)
        return user_id_list

    def update_total_user_id(self):
        total_user_id_media = set()
        total_user_id_follower = set()

        if self.media_username_list != settings.usernames_for_media_processing:
            if len(settings.usernames_for_media_processing):
                self.media_username_list = settings.usernames_for_media_processing
                self.media_user_id = self.get_user_id_list_otzberg(
                    self.media_username_list)
                total_user_id_media = self.get_total_user_id_set_media()
        if self.follower_username_list != settings.usernames_for_followers_processing:
            if len(settings.usernames_for_followers_processing):
                self.follower_username_list = settings.usernames_for_followers_processing
                self.follower_user_id = self.get_user_id_list_otzberg(
                    self.follower_username_list)
                total_user_id_follower = self.get_total_user_id_set_follower()
        self.total_user_id = self.total_user_id.union(
            total_user_id_follower, total_user_id_media)
        log_message = 'Размер аудитории: {}'.format(len(self.total_user_id))
        self.log(log_message)

    def load(self):
        if settings.new_account:
            self.time_multiply = 4
        else:
            self.time_multiply = 1
        self.load_log()
        self.set_proxy()
        if os.path.exists('save'):
            self.log('Перехожу в режим загрузки')
            self.log('Файл сохранения найден')
            with open('save', 'rb') as f:
                data = pickle.load(f)

            self.today_date = data['today_date']
            self.today_follows = data['today_follows']
            self.today_unfollows = data['today_unfollows']
            self.today_likes = data['today_likes']
            self.today_actions = data['today_actions']
            self.processed_users = data['processed_users']
            self.total_user_id = data['total_user_id']
            self.media_username_list = data['media_username_list']
            self.follower_username_list = data['follower_username_list']

            self.account_id = otzberg.get_user_id(settings.username)
            self.update_date(load_flag=True)
            self.update_total_user_id()
            self.log('Загрузка завершена')
        else:
            self.log('Файл сохранения не найден')
            self.today_date = datetime.datetime(1700, 1, 1)
            self.update_date()

            self.processed_users = deque()

            self.media_username_list = []
            self.follower_username_list = []
            self.total_user_id = set()
            self.update_total_user_id()
            self.log('Настройка параметров завершена')
        atexit.register(self.save)

    def save(self):
        data = {
            'today_date': self.today_date,
            'today_follows': self.today_follows,
            'today_unfollows': self.today_unfollows,
            'today_likes': self.today_likes,
            'today_actions': self.today_actions,
            'processed_users': self.processed_users,
            'total_user_id': self.total_user_id,
            'media_username_list': self.media_username_list,
            'follower_username_list': self.follower_username_list
        }
        with open('save', 'wb') as f:
            pickle.dump(data, f)
        self.log("Сохранил текущую сессию")

    def get_user_info(self, user_id, timer=4):
        time.sleep(random.uniform(self.time_multiply *
                                  timer/2, self.time_multiply*timer))
        self.api.getUsernameInfo(user_id)
        if self.api.LastJson.get('user') == None:
            if self.api.LastResponse.status_code == 400:
                return False
            timer = timer * 2
            if timer > 32:
                self.authorize()
                return False
            return self.get_user_info(user_id, timer=timer)
        return self.api.LastJson.get('user')

    def check_user(self, user_id):
        user_info_full = self.get_user_info(user_id)
        if user_info_full == False:
            return False
        log_message = "Проверяем {}".format(user_info_full['username'])
        self.log(log_message)
        user_follow_count = user_info_full['following_count']
        user_follower_count = user_info_full['follower_count']
        user_media_count = user_info_full['media_count']

        if settings.only_no_private and user_info_full['is_private']:
            return False
        elif settings.only_no_busy and user_info_full['is_business']:
            return False
        elif settings.only_with_profile_pic and user_info_full['has_anonymous_profile_picture']:
            return False
        elif user_follow_count < settings.following_min or user_follow_count > settings.following_max:
            return False
        elif user_follower_count < settings.follower_min or user_follower_count > settings.follower_max:
            return False
        elif user_media_count < settings.media_min:
            return False
        else:
            user_info = {
                'user_id': user_info_full['pk'],
                'username': user_info_full['username'],
                'following_count': user_info_full['following_count'],
                'follower_count': user_info_full['follower_count'],
                'media_count': user_info_full['media_count'],
                'is_private': user_info_full['is_private'],
                'is_business': user_info_full['is_business'],
                'is_anonymous': user_info_full['has_anonymous_profile_picture'],
                'time_follow': None,
                'time_unfollow': None,
                'together': None
            }
            return user_info

    def get_user_id_set_from_follower(self, follower_id_list):
        self.log("Собираю аудиторию по подписчикам")
        user_id_set = set()
        for user_id in follower_id_list:
            self.log("Собираю аудиторию у {}".format(user_id))
            followers = self.get_total_followers(user_id)
            for follower in followers:
                user_id_set.add(follower['pk'])
        self.log("Сбор аудитории по постам завершен")
        return user_id_set

    def get_total_followers(self, user_id, followers=[], next_max_id=''):
        while 1:
            self.api.getUserFollowers(user_id, next_max_id)
            temp = self.api.LastJson
            if temp['status'] == 'fail':
                time.sleep(45)
                break
            for user in temp["users"]:
                if settings.only_no_private and user['is_private'] == True:
                    continue
                elif settings.only_with_profile_pic:
                    if (not user.get('profile_pic_id', False) and
                            not user.get('has_anonymous_profile_picture', False)):
                        continue
                followers.append(user)
            if temp["big_list"] is False:
                return followers
            next_max_id = temp["next_max_id"]
        return self.get_total_followers(user_id, followers, next_max_id)

    def get_total_user_id_set_follower(self):
        return self.get_user_id_set_from_follower(self.follower_user_id)

    def get_total_user_id_set_media(self):
        self.log("Собираю аудиторию по постам")
        timestamp = self.get_timestamp_from_string(settings.media_end_date)
        total_media_id_list = []
        total_user_id_set = set()
        for user_id in self.media_user_id:
            self.log("Собираю аудиторию у {}".format(user_id))
            total_media_id_list += self.get_media_id_list(user_id, timestamp)
        return self.get_user_id_set_from_media(total_media_id_list)

    def get_media_id_list(self, user_id, timestamp=0):
        user_feed = self.api.getTotalUserFeed(user_id)
        media_id_list = []
        k = 0
        for media in user_feed:
            try:
                k += 1
                if media['caption']['created_at'] > timestamp:
                    media_id_list.append(media['id'])
                else:
                    break
            except TypeError:
                if media['taken_at'] > timestamp:
                    media_id_list.append(media['id'])
                else:
                    break
        return media_id_list

    def get_user_id_set_from_media(self, media_id_list):
        user_id_set = set()
        for media_id in media_id_list:
            self.api.getMediaLikers(media_id)
            for user in self.api.LastJson['users']:
                if settings.only_no_private and user['is_private'] == True:
                    continue
                elif settings.only_with_profile_pic:
                    if (not user.get('profile_pic_id', False) and
                            not user.get('has_anonymous_profile_picture', False)):
                        continue
                user_id_set.add(user['pk'])
        self.log("Сбор аудитории по постам завершен")
        return user_id_set

    def get_timestamp_from_string(self, date_string):
        y, m, d = date_string.split('-')
        dt = datetime.datetime(int(y), int(m), int(d))
        timestamp = time.mktime(dt.timetuple())
        return timestamp

    def follow(self, user_id):
        self.api.follow(user_id)

    def unfollow(self, user_id):
        self.api.unfollow(user_id)

    def like(self, media_id):
        self.api.like(media_id)

    def write_excel(self):
        pass

    def make_unfollow(self):
        if len(self.processed_users):
            self.log("Пробую найти аккаунты для отписки")
            time_now = datetime.datetime.now()
            while True:
                log_message = ''
                user_info = self.processed_users.popleft()
                delta_time = time_now - user_info['time_follow']
                if delta_time.days >= 3 and self.today_unfollows < 1000:
                    self.unfollow(user_info['user_id'])
                    self.today_unfollows += 1
                    user_info['time_unfollow'] = datetime.datetime.now()
                    time.sleep(random.uniform(
                        self.time_multiply*4, self.time_multiply*7))
                    self.write_excel()
                    log_message += 'Отписался от {}, отписок за сегодня={}/{}'.format(
                        user_info['username'],
                        self.today_unfollows,
                        1000
                    )
                    self.log(log_message)
                else:
                    self.processed_users.appendleft(user_info)
                    break

    def update_date(self, load_flag=False, limit_flag=False):
        self.log("Перехожу в режим смены дня")
        time_now = datetime.datetime.now()
        delta_time = time_now - self.today_date
        if delta_time.days >= 1:
            self.today_date = time_now
            self.today_follows = 0
            self.today_unfollows = 0
            self.today_likes = 0
            self.today_actions = 0
            self.account_id = otzberg.get_user_id(settings.username)
            self.log("День обновлен")
        elif load_flag or limit_flag:
            self.log("Продолжаю текущий день")
        else:
            self.log("Засыпаю на 10 минут, жду начала нового дня")
            time.sleep(600)
            return self.update_date()

    def processing(self):
        try:
            while True:
                if self.today_follows < settings.day_limit_follows or self.today_likes < settings.day_limit_likes:
                    try:
                        log_message = ''
                        user_id = self.total_user_id.pop()
                        user_info = self.check_user(user_id)
                        if user_info:
                            log_message += 'last user is {}, '.format(
                                user_info['username'])
                            if self.today_follows < settings.day_limit_follows:
                                self.follow(user_id)
                                self.today_follows += 1
                                user_info['time_follow'] = datetime.datetime.now()
                                time.sleep(random.uniform(
                                    self.time_multiply*26, self.time_multiply*36))
                                log_message += 'подписок за сегодня={}/{}, '.format(self.today_follows,
                                                                                    settings.day_limit_follows)
                            if not user_info['is_private']:
                                if self.today_likes < settings.day_limit_likes:
                                    media_id_list = self.get_media_id_list(
                                        user_id)
                                    media_id = random.choice(media_id_list)
                                    self.like(media_id)
                                    self.today_likes += 1
                                    time.sleep(random.uniform(
                                        self.time_multiply*3, self.time_multiply*7))
                                    log_message += 'лайков за сегодня={}/{} '.format(self.today_likes,
                                                                                     settings.day_limit_likes)
                            self.log(log_message)
                            self.processed_users.append(user_info)
                        self.today_actions += 1
                        if self.today_actions % 10 == 0:
                            self.save()
                        if self.today_actions % 3000 == 0:
                            self.make_unfollow()
                            self.update_date(limit_flag=True)
                    except Exception as e:
                        self.app_log.exception("")
                        if str(e).strip() == "Not logged in!":
                            self.authorize()
                        else:
                            self.log(traceback.format_exc())
                            sys.exit()
                else:
                    self.update_date()
        except Exception as e:
            self.app_log.exception("")
            self.log(traceback.format_exc())
            sys.exit()

    def load_log(self):
        log_formatter = logging.Formatter('[%(asctime)s] - %(message)s',
                                          "%Y-%m-%d %H:%M:%S")

        my_handler = RotatingFileHandler("log", maxBytes=128*1024,
                                         backupCount=1, encoding=None, delay=0)
        my_handler.setFormatter(log_formatter)
        my_handler.setLevel(logging.INFO)

        self.app_log = logging.getLogger('root')
        self.app_log.setLevel(logging.INFO)

        self.app_log.addHandler(my_handler)

    def log(self, msg):
        self.app_log.info(msg)
        print("[{}] [{}] {}".format(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                                    settings.username, msg))


if __name__ == "__main__":
    account = InstagramFish()
    account.authorize()
    account.load()
    account.processing()
