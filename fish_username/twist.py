import settings
import sys
sys.path.insert(0, '../')
import otzberg
from instagram import InstagramFish


account = InstagramFish()
account.authorize()
account.load()
account.processing()
