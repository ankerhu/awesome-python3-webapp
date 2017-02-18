#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging;logging.basicConfig(level=logging.INFO)
import orm
from models import User
async def test(loop):
    await orm.create_pool(loop=loop,host='127.0.0.1', port=3306, user='root', password='password', db='awesome')
    u = User(name='xiaopeng', email='chenhao8@qq.com', passwd='1234567890', image='about:blank')
    await u.save()
    logging.info('tesk ok')
if __name__ =='__main__':
    loop = asyncio.get_event_loop()

    loop.run_until_complete(test(loop))

    loop.close()