# -*- coding: utf-8 -*-
import sys,os,fnmatch
import subprocess

if __name__ == '__main__':
  runs = []
  if os.path.isfile(sys.argv[1]):
    if sys.argv[1][-4:] == 'root':
      runs.append(sys.argv[1])
    elif sys.argv[1][-8:] == 'filelist':
      f = open(sys.argv[1],'r')
      files = f.readlines()
      runs = [file[:-1] for file in files] 
  elif os.path.isdir(sys.argv[1]):
    files = fnmatch.filter(os.listdir(sys.argv[1]),'????????_???.root')
    files.sort()
    for file in files:
      runs.append(sys.argv[1]+file)
  for file in runs:
    subprocess.call(['time','python','runFeldbergKamper.py',file,sys.argv[2],sys.argv[3]])
