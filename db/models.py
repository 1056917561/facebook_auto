#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by Charles on 19-3-16
# Function: 任务调度模块相关表结构定义， 可通过执得本脚本在数据库中直接创建或删除表


from sqlalchemy import (
    Column, Integer, String, DateTime, Table, ForeignKey)
from sqlalchemy.orm import relationship
from db.basic import Base, engine


class User(Base):
    __tablename__ = 'user'
    __table_args__ = {"useexisting": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    # account = Column(String(255), unique=True)
    # password = Column(String(255))
    # name = Column(String(255), default='', server_default='')
    category = Column(Integer, ForeignKey('user_category.category'))
    token = Column(String(255), default='', server_default='')
    # 记录该用户可以创建的[任务类型id]列表(TaskCategory.id)， 以分号分割"1;2;3", 默认为空，代表可以创建所有类型的任务
    enable_tasks = Column(String(255), default='', server_default='')


class UserCategory(Base):
    __tablename__ = 'user_category'
    # 用户身份，1-普通用户，2-管理员
    category = Column(Integer, primary_key=True)
    name = Column(String(255))  # 类别名称，如普通用户，管理员...
    description = Column(String(255), default='', server_default='')


class Scheduler(Base):
    __tablename__ = 'scheduler'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 执行模式： 0-立即执行（只执行一次）， 1-间隔执行并不立即开始（间隔一定时间后开始执行，并按设定的间隔周期执行下去） 2-间隔执行，但立即开始， 3-定时执行，指定时间执行
    mode = Column(Integer, default=0, server_default='0')
    interval = Column(Integer, default=600, server_default='0')       # 间隔时长， 单位秒
    date = Column(DateTime(3))       # 定时执行时需要指定，如2019-03-31 13:30:30

    def __repr__(self):
        return "id:{}, mode:{}, interval:{}, date:{}. ".format(
            self.id, self.mode, self.interval, self.date)


task_account_group_table = Table(
    'task_account_group', Base.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('task_id', Integer, ForeignKey("task.id")),
    Column('account_id', Integer, ForeignKey("account.id")),
    # 这个是在APScheduler中调度时的任务id, 用以暂停、重启、终止等 操作,一个任务+一个账号构成一个唯一的task
    Column('aps_id', String(100)),
    Column('next_run_time', DateTime(3))
)


class TaskAccountGroup(Base):
    __table__ = task_account_group_table


class TaskCategory(Base):
    """
    任务类型表
    """
    __tablename__ = 'task_category'
    # 1--fb自动养账号， 2-fb刷广告好评， 3- fb仅登录浏览， 4- fb点赞, 5- fb发表评论， 6- fb post状态, 7- fb 聊天， 8- fb 编辑个人信息， 未完待续...
    category = Column(Integer, primary_key=True)
    name = Column(String(255))
    processor = Column(String(255))  # 任务的处理函数名, 不能为空, 代码逻辑中将依赖这个函数名进行任务分发
    description = Column(String(2048), default='', server_default='')


class Task(Base):
    """
    任务表， 对用户层承现
    """
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), default='', server_default='')

    # 任务类型， 0-养账号，1-刷好评,其他待续
    category = Column(Integer, ForeignKey('task_category.category'))

    # 任务状态， -1-pending, 0-failed, 1-succeed, 2-running, 3-pausing, new-新新，还没处理
    # status = Column(Integer, default=-1, server_default='-1')
    # 任务状态改用字符串是为了直观， 避免前后端转换的麻烦
    status = Column(String(20), default='new', server_default='new')

    # 任务的创建者
    creator = Column(Integer, ForeignKey('user.id'))

    # 任务调度规则
    scheduler = Column(Integer, ForeignKey('scheduler.id'))

    # 一个任务同时占用多个账号
    accounts = relationship('Account',
                            secondary=task_account_group_table)  # ,
    # back_populates='parents')

    # 第一次真正启动的时间
    start_time = Column(DateTime(3), default=None)

    # 实际结束时间
    end_time = Column(DateTime(3), default=None)

    # 该task成功、失败的次数（针对周期性任务）
    failed_counts = Column(Integer, default=0, server_default='0')
    succeed_counts = Column(Integer, default=0, server_default='0')

    # 该任务最大执行次数（即成功的job次数），比如刷分，可以指定最大刷多少次
    limit_counts = Column(Integer, default=1, server_default='1')

    # 该任务最晚结束时间， 主要针对阶段性任务
    limit_end_time = Column(DateTime(3), default=None)

    result = Column(String(2048), default='', server_default='')

    # 这里保存任务的额外信息，以json字符形式保存，如post内容， 点赞规则, ads_code, keep time, 目标站点等
    configure = Column(String(2048), default='', server_default='')




    def accounts_list(self):
        return [acc.account for acc in self.accounts]

    def __repr__(self):
        return "id:{}, name:{}, category:{}, status:{}, creator:{}, scheduler:{}, accounts:{}, description:{}, " \
               "errors:{}. ".format(self.id, self.name, self.category, self.status, self.creator, self.scheduler,
                                    self.accounts_list(), self.configure, self.result)


class Job(Base):
    """
    每一个task都将被分解成多个job, 一个job才是真正的可执行单元
    """
    __tablename__ = 'job'
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 一个任务加一个唯一的account构成一个job
    task = Column(Integer, ForeignKey('task.id'))
    account = Column(Integer, ForeignKey('account.id'))

    # 这个任务被分配到了哪个agent上，用上计算agent的负载
    agent = Column(Integer, ForeignKey('agent.id'))

    # -1-pending, 0-failed, 1-succeed, 2-running
    # status = Column(Integer, default=-1, server_default='-1')
    status = Column(String(20), default='pending', server_default='pending')

    # 这个job执行时被分配的id,用以在结果队列中跟踪job执行情况
    track_id = Column(String(255), default='', server_default='', unique=True)

    start_time = Column(DateTime(3))
    end_time = Column(DateTime(3))

    # job执行函数的返回值
    result = Column(String(2048), default='', server_default='')
    traceback = Column(String(2048), default='', server_default='')

    def __repr__(self):
        return "id:{}, task:{}, account:{}, start_time:{}, status:{}, result:{}. ".format(
            self.id, self.task, self.account, self.start_time, self.status, self.result)

#
# class Action(Base):
#     __tablename__ = 'action'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String(255), default='', server_default='')
#     depend_on = Column(Integer, ForeignKey('action.id'), default=None)
#
#
# class JobActions(Base):
#     __tablename__ = 'job_actions'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     job_id = Column(Integer, ForeignKey('job.id'))
#     action_id = Column(Integer, ForeignKey('action.id'))
#     result = Column(String(255), default='', server_default='')
#


class Account(Base):
    __tablename__ = 'account'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 该账号所属类别，该账号所属类别，1--facebook账号，2--twitter账号， 3--Ins账号
    category = Column(Integer, ForeignKey('account_category.category'))

    # 每个账号都应该隶属于某个人员，以方便权限管理
    owner = Column(Integer, ForeignKey('user.id'))
    account = Column(String(255))
    password = Column(String(255))
    # -----------------以上是必填项----------------

    email = Column(String(255), default='', server_default='')
    email_pwd = Column(String(255), default='', server_default='')
    phone_number = Column(String(100), default='', server_default='')

    # 0-女，1-男
    gender = Column(Integer, default=0, server_default='0')
    # 生日格式"1990-3-21"
    birthday = Column(String(100), default='', server_default='')
    national_id = Column(String(100), default='', server_default='')
    register_time = Column(String(100), default='', server_default='')
    name = Column(String(100), default='', server_default='')
    profile_id = Column(String(100), default='', server_default='')

    # 0-valid, 1-invalid, 2-verify, 3-other
    status = Column(String(20), default='valid', server_default='valid')

    # 是否正在被某任务使用 0-未使用， 大于1代表正在被使用，数字代表并发使用数
    using = Column(Integer, default=0, server_default='0')

    # 记录该用户可以创建的[任务类型id]列表(TaskCategory.id)， 以分号分割"1;2;3", 默认为空，代表可以创建所有类型的任务
    enable_tasks = Column(String(255), default='', server_default='')

    # 存放用户profile文件
    profile_path = Column(String(255), default='', server_default='')

    last_login = Column(DateTime(3))
    last_post = Column(DateTime(3))
    last_chat = Column(DateTime(3))
    last_farming = Column(DateTime(3))
    last_comment = Column(DateTime(3))
    last_edit = Column(DateTime(3))

    # active_ip = Column(String(255), default='', server_default='')
    # 活跃地域
    active_area = Column(String(255), default='', server_default='')
    # 常用浏览器指纹
    active_browser = Column(String(2048), default='', server_default='')
    # 一个账号有可能同是被多个任务占用，逻辑上是可以的， 但实际操作上应该尽量避免此种情况，以规避多IP同时登录带来的封号风险
    tasks = relationship("Task", secondary=task_account_group_table)  # ,back_populates='children')

    # 账号的其他非常规配置信息
    configure = Column(String(2048), default='', server_default='')

    def __repr__(self):
        return "id:{}, account:{}, password:{}, email={}, email_pwd:{}, gender:{}, birthday:{}, national_id:{}, " \
               "register_time:{}, name:{}, profile_id:{}, status:{}, owner:{}, usage:{}, last_login:{}, last_post:{}, " \
               "las_chat:{}, last_comment:{}, last_farming:{}, last_edit:{}, tasks:{}, profile_path:{}. ".format(
                   self.id, self.account, self.password, self.email, self.email_pwd, self.gender, self.birthday,
                   self.national_id, self.register_time, self.name, self.profile_id, self.status, self.owner,
                   self.usage, self.last_login, self.last_post, self.last_chat, self.last_comment, self.last_farming,
                   self.last_edit, self.tasks, self.profile_path)


class AccountCategory(Base):
    """
    账号类型表
    """
    __tablename__ = 'account_category'
    # 该账号所属类别，1--facebook账号，2--twitter账号， 3--Ins账号
    category = Column(Integer, primary_key=True)
    name = Column(String(255), default='', server_default='')


class Agent(Base):
    __tablename__ = 'agent'
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 该agent绑定的任务队列， job将根据与其最亲近的agent的queue名来被分发, 通常队列名与area相同
    queue_name = Column(String(255), default='', server_default='')

    # 0-idle, 1-normal, 2-busy, 3-disable
    # -1--disable, 大于零代表其忙碌值（即当前待处理的任务量）
    status = Column(String(20), default=0, server_default='0')

    # 该agent所属区域
    area = Column(String(255), default='', server_default='')

    # 该agent的配置信息
    configure = Column(String(2048), default='', server_default='')


class Area(Base):
    __tablename__ = 'area'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    description = Column(String(2048), default='', server_default='')


if __name__ == '__main__':
    while True:
        res = input("What do you want to do, create or drop? \n")
        if res == 'drop':
            res = input("Are you sure? \n")
            if res.lower().startswith('y'):
                Base.metadata.drop_all(engine)
            break
        elif res == 'create':
            Base.metadata.create_all(engine)
            break
        elif res == 'exit':
            break
        else:
            pass

    print("finished.")
