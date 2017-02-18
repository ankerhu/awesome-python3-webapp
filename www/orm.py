#!/usr/bin/env python3
#-*- coding:utf-8 -*-

__author__='Ankerhu'
'''
orm
'''
import asyncio
import logging
import aiomysql
def log(sql,args=()):
	logging.info('SQL:%s'%sql)
async def destroy_pool():
	global __pool
	if __pool is not None:
		__pool.close()
		await __pool.wait_closed()
#创建连接池
async def create_pool(loop,**kw):
	logging.info('create database connection pool....')
	global __pool
	__pool = await aiomysql.create_pool(
		host=kw.get('host','localhost'),
		port=kw.get('port',3306),
		user=kw['user'],
		password=kw['password'],
		db=kw['db'],
		charset=kw.get('charset','utf8'),
		autocommit=kw.get('autocommit',True),
		maxsize=kw.get('maxsize',10),
		minsize=kw.get('minsize',1),
		#接收一个event_loop实例
		loop=loop,
	)
#封装SQL SELECT语句为select函数
async def select(sql,args,size=None):
	log(sql,args)
	global __pool
	async with __pool.get() as conn:
		# DictCursor is a cursor which returns results as a dictionary
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?','%s'),args or ())
				if size:
					rs=await cur.fetchmany(size)
				else:
					rs=await cur.fetchall()
				await cur.close()	
		except BaseException as e:
			raise
		finally:
			conn.close()
		logging.info('rows returned:%s' % len(rs))
		return rs
#Insert，update，delete语句，操作参数一样，定义一个通用执行函数即可
#返回操作影响的行号
async def execute(sql,args,autocommit=True):
	log(sql)
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', '%s'), args)
				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				await conn.rollback()
			raise
		finally:
			conn.close()
		return affected
#根据输入的参数生成占位符列表
def create_args_string(num):
	L=[]
	for n in range(num):
		L.append('?')
	return ','.join(L)

#定义Field类，负责保存(数据库)表的字段名和字段类型
class Field(object):
	# 表的字段包含名字、类型、是否为表的主键和默认值
	def __init__(self,name,column_type,primary_key,default):
		self.name=name
		self.column_type=column_type
		self.primary_key=primary_key
		self.default=default
	# 当打印(数据库)表时，输出(数据库)表的信息:类名，字段类型和名字
	def __str__(self):
		return '<%s,%s:%s>' % (self.__class__.__name__,self.column_type,self.name)
#映射varchar的StringField:
class StringField(Field):
	def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)
#映射布尔值
class BooleanField(Field):
	def __init__(self,name=None,default=False):
		super().__init__(name,'boolean',False,default)
#映射整数
class IntegerField(Field):
	def __init__(self,name=None,primary_key=False,default=0):
		super().__init__(name,'bigint',primary_key,default)
#映射小数
class FloatField(Field):
	def __init__(self,name=None,primary_key=False,default=0.0):
		super().__init__(name,'real',primary_key,default)
#映射文本
class TextField(Field):
	def __init__(self,name=None,default=None):
		super().__init__(name,'text',False,default)
#元类mataclass
#在当前类中查找所有的类属性(attrs)，如果找到Field属性，就将其保存到__mappings__的dict中，同时从类属性中删除Field(防止实例属性遮住类的同名属性)
#将数据库表名保存到__table__中
class ModelMetaclass(type):
	
	# __new__控制__init__的执行，所以在其执行之前
    # cls:代表要__init__的类，此参数在实例化时由Python解释器自动提供(例如下文的User和Model)
    # bases：代表继承父类的集合
    # attrs：类的方法集合
	def __new__(cls,name,bases,attrs):
		#排除model类本身
		if name=='Model':
			return type.__new__(cls,name,bases,attrs)
		#获取table名称：
		tableName = attrs.get('__table__',None) or name
		logging.info('found model:%s(table:%s)'%(name,tableName))
		#获取所有Field和主键名
		mappings=dict()
		fields=[]		
		primaryKey=None
		for k,v in attrs.items():
			# Field 属性
			if isinstance(v,Field):
				# 此处打印的k是类的一个属性，v是这个属性在数据库中对应的Field列表属性
				logging.info('  found mapping:%s==>%s'%(k,v))
				mappings[k]=v
				#找到主键
				if v.primary_key:
					# 如果此时类实例的已存在主键，说明主键重复了
					if primaryKey:
						raise StandardError('Duplicate primary key for field:%s'%k)
					# 否则将此列设为列表的主键
					primaryKey=k
				else:
					#不是主键的放到field中
					fields.append(k)
		if not primaryKey:
			raise StandardError('Primary key not found.')
		# 从类属性中删除Field属性
		for k in mappings.keys():
			attrs.pop(k)
		# 保存除主键外的属性名为``（运算出字符串）列表形式
		escaped_fields=list(map(lambda f:'`%s'%f,fields))
		#保存属性和列的映射关系
		attrs['__mappings__']=mappings
		#保存表名
		attrs['__table__']=tableName
		#保存主键属性名
		attrs['__primary_Key__']=primaryKey
		#保存除主键外的属性名
		attrs['__fields__']=fields
		#构造默认的SELECT，INSERT，UPDATE和DELETE语句
		# ``反引号功能同repr()
		attrs['__select__']='select `%s`,%s from `%s`'%(primaryKey,','.join(escaped_fields),tableName)
		attrs['__insert__']='insert into `%s` (%s,`%s`) values (%s)'%(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
		attrs['__update__']='update `%s` set %s where `%s`=?'%(tableName,','.join(map(lambda f:'`%s`=?'%(mappings.get(f).name or f),fields)),primaryKey)
		attrs['__delete__']='delete from `%s` where `%s`=?'%(tableName,primaryKey)
		return type.__new__(cls,name,bases,attrs)

# 定义ORM所有映射的基类：Model
# Model类的任意子类可以映射一个数据库表
# Model类可以看作是对所有数据库表操作的基本定义的映射

# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict,metaclass=ModelMetaclass):
	def __init__(self,**kw):
		super(Model,self).__init__(**kw)
	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)
	def __setattr__(self,key,value):
		self[key]=value
	def getValue(self,key):
		#由内建函数getattr自动处理
		return getattr(self,key,None)
	def getValueOrDefault(self,key):
		value = getattr(self,key,None)
		if value is None:
			field = self.__mappings__[key]
			if field.default is not None:
				value=field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s:%s' % (key,str(value)))
				setattr(self,key,value)
		return value
	@classmethod
	# 类方法有类变量cls传入，从而可以用cls做一些相关的处理。并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。
	async def findAll(cls,where=None,args=None,**kw):
		'find objects by where clause.'
		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []
		orderBy = kw.get('orderBy',None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit)==2:
				sql.append('?,?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value:%s'%str(limit))
		rs=await select(' '.join(sql),args)
		return [cls(**r) for r in rs]
	@classmethod
	async def findNumber(cls,selectField,where=None,args=None):
		'find number by select and where.'
		sql=['select %s _num_ from `%s`' %(selectField,cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs=await select(' '.join(sql),args,1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']
	@classmethod
	async def find(cls,pk):
		'find object by primary key'
		rs=await select('%s where `%s`=?' % (cls.__select__,cls.__primary_Key__),[pk],1)
		if len(rs)==0:
			return None
		return cls(**rs[0])

	async def save(self):
		args = list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_Key__))
		rows=await execute(self.__insert__,args)
		if rows !=1:
			logging.warn('failed to insert record:affected rows:%s'%rows)
	async def update(self):
		args=list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_Key__))
		rows=await execute(self.__update__,args)
		if rows !=1:
			logging.warn('faild to update by primary key:affected rows:%s'%rows)
	async def remove(self):
		args = [self.getValue(self.__primary_Key__)]
		rows=await execute(self.__delete__,args)
		if rows !=1:
			logging.warn('faild to remove by primary key: affected rows:%s'%rows)
