#!/usr/bin/env python

import subprocess
import tempfile
import wsgiref
import logging
log = logging.getLogger(__name__)

from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado.wsgi import WSGIApplication
from tornado.options import parse_command_line, options, define

import utils

#AppType = WSGIApplication
AppType = Application

pack_ops = {
    'git-upload-pack': 'upload-pack',
    'git-receive-pack': 'receive-pack',
}

class rpc_service(RequestHandler):
    @utils.clense_path
    def post(self, repo, op):
        log.debug('rpc_service')

        indata = self.request.body

        utils.hdr_nocache(self)

        self.set_header('Content-Type', 'application/x-%s-result' % (op))

        proc = subprocess.Popen([git, pack_ops[op], '--stateless-rpc',
            '%s/%s' % (base, repo)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        proc.stdin.write(indata)
        proc.wait()

        while True:
            outdata = proc.stdout.read(8192)
            if outdata == '':
                return
            self.write(outdata)
            self.flush()

class get_objects(RequestHandler):
    @utils.clense_path
    def get(self, repo, obj_file):
        log.debug('get_objects')

        self.set_header('Content-type', 'application/x-git-loose-object')
        with open('{}/{}/{}'.format(base, repo, obj_file)) as f:
            self.write(f.read())

class get_refs_info(RequestHandler):
    @utils.clense_path
    def get(self, repo):
        log.debug('get_refs_info')

        service = self.get_argument('service', default=None)
        if service is not None:
            log.debug('looks like smart http')
            self.set_header('Content-type', 'application/x-%s-advertisement' % (
                service))

            ret = utils.mk_pkt_line('# service=%s\n%s' % (
                service, utils.pkt_flush()))

            ret = '%s%s' % (ret, subprocess.check_output([git,
                pack_ops[self.get_argument('service')],
                '--stateless-rpc', '--advertise-refs', '%s/%s' % (base, repo)]))
            ret = ret.strip()
        else:
            log.debug('looks like dumb http')
            subprocess.check_call([git, 'update-server-info'],
                    cwd='{}/{}'.format(base, repo))
            self.set_header('Content-type', 'text/plain; charset=utf-8')
            with open('{}/{}/info/refs'.format(base, repo)) as f:
                ret = ''.join(f.readlines())

        utils.hdr_nocache(self)
        self.write(ret)

class text_file(RequestHandler):
    @utils.clense_path
    def get(self, repo, path):
        log.debug('text_file: %s'% (path))

        self.set_header('Content-type', 'text/plain')
        with open('%s/%s/%s' % (base, repo, path)) as f:
            self.write(f.read())

application = AppType([
    (r'/(.*?)/(git-upload-pack|git-receive-pack)', rpc_service),
    (r'/(.*?)/(objects/[0-9a-f]{2}/[0-9a-f]{38}$)', get_objects),
    (r'/(.*?)/info/refs', get_refs_info),
    (r'/(.*?)/(HEAD)', text_file),
    (r'/(.*?)/(objects/info/[^/]*$)', text_file),
    ],debug=True)

if __name__ == '__main__':
    define("base", default='/tmp/repo',
            help='The base repository dir (default = /tmp/repo)')
    define('git', default='/usr/bin/git',
            help='path to git binary (default = /usr/bin/git)')
    parse_command_line()

    git = options.git
    base = options.base

    if isinstance(application, WSGIApplication):
        server = wsgiref.simple_server.make_server('', 8888, application)
        server.serve_forever()
    else:
        application.listen(8080)
        IOLoop.instance().start()
        # foo
