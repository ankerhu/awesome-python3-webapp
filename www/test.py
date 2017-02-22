#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging;logging.basicConfig(level=logging.INFO)
import orm
from models import User
async def test(loop):
    await orm.create_pool(loop=loop, host='localhost', port=3306, user='www-data', password='www-data', db='awesome')
    u = User(name='Test19', email='test19@example.com', passwd='123456',image='about:blank')
    await u.save()
    logging.info('tesk ok')
if __name__ =='__main__':
    loop = asyncio.get_event_loop()

    loop.run_until_complete(test(loop))

    loop.close()