"""Forward MSVC status and normalize Chinese include diagnostics for Ninja."""
# SPDX-License-Identifier: AGPL-3.0-only
import ctypes
import hashlib
import os
import subprocess
import sys


def normalize(data,encoding):
    try:text=data.decode('utf-8')
    except UnicodeDecodeError:text=data.decode(encoding,errors='replace')
    prefix='\u6ce8\u610f: \u5305\u542b\u6587\u4ef6:'
    if text.startswith(prefix):text='Note: including file:'+text[len(prefix):]
    return text.encode('utf-8')


def main():
    args=sys.argv[1:]
    if args and args[0].startswith('--source-sha256='):
        expected=args.pop(0).split('=',1)[1]
        with open(__file__,'rb') as source:actual=hashlib.sha256(source.read()).hexdigest()
        if actual!=expected:return 2
    if not args:return 2
    encoding='cp'+str(ctypes.windll.kernel32.GetACP()) if os.name=='nt' else 'utf-8'
    child=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in iter(child.stdout.readline,b''):
        sys.stdout.buffer.write(normalize(line,encoding));sys.stdout.buffer.flush()
    return child.wait()


if __name__=='__main__':sys.exit(main())
