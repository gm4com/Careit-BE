import logging
import os
import subprocess
# from multiprocessing import Process

from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall

from common.utils import SingletonOptimizedMeta


"""
큐와 큐에 들어온 명령어(푸쉬)를 수행하는 로직
/etc/rc.local 에 추가하여
실행시켜야 함
"""


logger = logging.getLogger('queued')


class QueueHandler(metaclass=SingletonOptimizedMeta):
    codes = []

    def handle(self):
        while self.codes:
            code, id = self.codes.pop().split(':')
            if code == 'PUSH':
                self.handle_PUSH(id)

    def handle_PUSH(self, id):
        notifier = subprocess.Popen(
            ('nohup ./venv/bin/python3 manage.py notify push %s' % id).split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,
            close_fds=True
        )
        # logger.info('%s : %s\n%s' % (notifier.pid, notifier.stderr, '\n'.join(notifier.stdout.readlines())))
        print(id)

    def add(self, id):
        self.codes.insert(0, id)


queue = QueueHandler()


class QueueProtocol(protocol.Protocol):

    def dataReceived(self, data):
        try:
            data = data.decode()
        except:
            return
        logger.info('Data Received :', data)
        if ':' in data:
            queue.add(data)

    def connectionMade(self):
        pass


LoopingCall(queue.handle).start(5)

factory = protocol.ServerFactory()
factory.protocol = QueueProtocol
reactor.listenTCP(8700, factory)
print('Listening 8700 port...')
reactor.run()
print('Closed 8700 port...')



# from notification.models import *
# q = QueueRegisterer()
# for i in range(0,10): q.push(i)
