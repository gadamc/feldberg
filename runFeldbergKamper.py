#!/usr/bin/env python
import ROOT
import json
import KDataPy.database as kdb
import sys,  datetime,  os, fnmatch, string, time, subprocess, signal, getpass
import numpy as np
import matplotlib.pyplot as plt
import couchdbkit
plt.ion()

#heatChanList = {"chalA FID807":512, "chalB FID807":512, "chalA FID808":512, "chalB FID808":512}

    
def submitBatch(runName):

  scriptDir = '/sps/edelweis/adam/feldberg'
  script =   os.path.join(scriptDir, 'runFeldbergKamper.py')
  scriptOut = os.path.join(scriptDir, 'batchOut')
  scriptErr = os.path.join(scriptDir, 'batchErr')
  dataOut= os.path.join(scriptDir, 'dataOut')

  try:
    db = kdb.kdatadb(serverName = 'http://localhost:5984')
    print db.info()
  except:
    db = kdb.kdatadb()
    print db.info()

  vr = db.view('proc/raw', key=runName)
  for row in vr:
    doc = row['doc']
    intputFile = doc['proc1']['file']
    outputFile = os.path.join(dataOut, os.path.basename(inputFile).strip('.root') + '.feldberg.root')

    command = 'qsub -P P_edelweis -o %s -e %s -l sps=1 -l vmem=15G -l fsize=11000M  %s %s %s %s' % (scriptOut, scriptErr, script, runName, inputFile, outputFile ) 
  
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,)
    val = proc.communicate()[0]
    if val != '':
      print val

def runProcess(runName, inputFile, outputFile):


  kounselor = ROOT.KAmpKounselor()
  try:
    db = kdb.kdatadb(serverName = 'http://localhost:5984')
    print db.info()
  except:
    db = kdb.kdatadb()
    print db.info()

  ionChanList = {}
  heatChanList = {}

  vr = db.view('proc/raw', limit=1, key=runName, include_docs=True)
  doc = vr.first()['doc']

  #when Michel updates Samba to write to couch, we'll have to push a 
  #switch here because the Samba docs are not the same as the
  #kdata docs in the database... ugg.
  for channel in doc['Voies']:
    if channel['Voie'].startswith('ionis'):
      ionChanList[channel['Voie']] = channel['Voie.lngr']
    elif channel['Voie'].startswith('chal') and channel['Voie'].find('Gc') == -1:
      heatChanList[channel['Voie']] = channel['Voie.lngr']

  try:
    db = kdb.kmultiprocdb(serverName = 'http://localhost:5984')
    print db.info()
  except:
    db = kdb.kmultiprocdb()
    print db.info()

  #this is the list of filters to applied separately to the different heat channels
  vr = db.view('channel/bydate', reduce=False,startkey=["scanFilters_binwidth2.016ms",""], limit=1, include_docs=True)
  doc = vr.first()['doc']['ana']['multiFilterAndCorr'][0]

  templatParamDoc = db[doc['templateparams']]

  width = templatParamDoc['templatewidth']
  pretrigger = templatParamDoc['pretrigger']
  delta_t = templatParamDoc['delta_t']
  heatFilters = doc['filters']
  
  #all of the heat channels in all kampsites will employ this lowpass filter
  lowPassDoc = db['lp_butterworth_2order_50.0Hz_binwidth2.016ms']
  lowPass_A = np.array(lowPassDoc['coef']['a'][1:])
  lowPass_B = np.array(lowPassDoc['coef']['b'])

  
  feldberglist = []
  for f in heatFilters:
    print ''
    print 'new feldberg kampsite --', f

    fbk = ROOT.KFeldbergKAmpSite()
        
    try:
      server = couchdbkit.Server('http://localhost:5984')
      db_template = server['pulsetemplates']
      print db_template.info()
    except:
      server = couchdbkit.Server('http://edwdbik.fzk.de:5984')
      db_template = server['pulsetemplates']
      print db_template.info()

    feldberglist.append(fbk)

    for chan in heatChanList.keys(): #set up the heat channels
      
      print "Set settings for channel:", chan, " pulse length:", heatChanList[chan]
      vr_template = db_template.view('analytical/bychandate', descending=True, reduce=False, startkey=[chan,'2013'], limit=1, include_docs=True)

      doc_template = vr_template.first()['doc']
      exec(doc_template['formula']['python'])

      templatePulse = ROOT.std.vector("double")()
      
      #assuming this is just for heat pulses for now... 
      for i in range(heatChanList[chan]):
        templatePulse.push_back( template(i*2.016, doc_template['formula']['par']))

      highPassDoc = db[f]
      
      fbk.AddIIRFilter(chan, lowPass_A.astype(float), len(lowPass_A), lowPass_B.astype(float), len(lowPass_B) ) #everybody gets a 50 Hz lowpass filter.
      fbk.AddIIRFilter(chan,np.array(highPassDoc['coef']['a'][1:]).astype(float),len(highPassDoc['coef']['a'][1:]),np.array(highPassDoc['coef']['b']).astype(float),len(highPassDoc['coef']['b']))
      fbk.AddLowPassIIRFilterInfo(lowPassDoc['order'], lowPassDoc['frequencies'][0])
      fbk.AddHighPassIIRFilterInfo(highPassDoc['order'], highPassDoc['frequencies'][0])

      print '    heatFilters', 'low:', lowPassDoc['order'], lowPassDoc['frequencies'][0], 'high:',highPassDoc['order'], highPassDoc ['frequencies'][0] 

      fbk.SetPeakFixedPositionForBckgdAmp(chan,265);
      fbk.SetNormalizeTemplate(True)
      fbk.SetTemplate(chan,templatePulse,pretrigger,delta_t,width)
      #fbk.SetDoFit(True)
      fbk.SetPeakPositionSearchRange(chan,240,290)

    for chan in ionChanList.keys():
      print "Set settings for channel:", chan, " pulse length:", ionChanList[chan]
      vr_template = db_template.view('analytical/bychandate', descending=True, reduce=False, startkey=[chan,'2013'], limit=1, include_docs=True)

      doc_template = vr_template.first()['doc']
      exec(doc_template['formula']['python'])

      templatePulse = ROOT.std.vector("double")()
      
      for i in range(ionChanList[chan]):
        templatePulse.push_back( template(i, doc_template['formula']['par']))


      vr = db.view('channel/bydate', descending=True, reduce=False,startkey=[chan,'2013'], limit=1, include_docs=True)
      doc = vr.first()['doc']['ana']['multiFilterAndCorr'][0] 
    
      templatParamDoc = db[doc['templateparams']]

      ionwidth = templatParamDoc['templatewidth']
      ionpretrigger = templatParamDoc['pretrigger']
      iondelta_t = templatParamDoc['delta_t']
      ionfilters = doc['filters']

      for f in ionfilters:
        filterDoc = db[f]
        print '        ', filterDoc['bandtype'], filterDoc['order'], filterDoc['frequencies'][0] 

        fbk.AddIIRFilter(chan,np.array(filterDoc['coef']['a'][1:]).astype(float),len(filterDoc['coef']['a'][1:]),np.array(filterDoc['coef']['b']).astype(float),len(filterDoc['coef']['b']))
        if filterDoc['bandtype'] == 'lowpass':
          fbk.AddLowPassIIRFilterInfo(filterDoc['order'], filterDoc['frequencies'][0])
        elif filterDoc['bandtype'] == 'highpass':
          fbk.AddHighPassIIRFilterInfo(filterDoc['order'], filterDoc['frequencies'][0])

      fbk.SetPeakFixedPositionForBckgdAmp(chan,5000);
      fbk.SetNormalizeTemplate(True)
      fbk.SetTemplate(chan,templatePulse,ionpretrigger,iondelta_t,ionwidth)
      #fbk.SetDoFit(True)
      fbk.SetPeakPositionSearchRange(chan,2191,6191)

    kounselor.AddKAmpSite(fbk)
  
  
  
  print "KAmpSite is set up"
  starttime = datetime.datetime.now()
  print 'now', starttime
  theRet = kounselor.RunKamp(inputFile,  outputFile)
  endtime = datetime.datetime.now()
  print 'end time', endtime
  print 'elapsed time', endtime - starttime


   
if __name__ == '__main__':
  runProcess(sys.argv[1], sys.argv[2], sys.argv[3])

  
