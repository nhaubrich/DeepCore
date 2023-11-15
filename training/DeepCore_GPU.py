from __future__ import print_function
import os
#os.environ['MKL_NUM_THREADS'] = '40'
#os.environ['GOTO_NUM_THREADS'] = '40'
#os.environ['OMP_NUM_THREADS'] = '40'
#os.environ['openmp'] = 'True'

import tensorflow as tf

from tensorflow.python.framework import ops
from tensorflow.python.ops import clip_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import nn
##import pdb ## for debug stuff

##
keras = tf.keras
##import keras
##from keras.backend import tensorflow_backend as K
import tensorflow.keras.backend as K
##

from keras.callbacks import Callback
from keras.models import Model,load_model, Sequential
from keras.layers import Input, LSTM, Dense, Flatten, Conv2D, MaxPooling2D, Dropout, Reshape, Conv2DTranspose, concatenate, Concatenate, ZeroPadding2D, UpSampling2D, UpSampling1D
from keras.optimizers import *
from keras.initializers import *
from keras.callbacks import ModelCheckpoint

import numpy as np
from numpy import concatenate as concatenatenp

import math
import sys
import argparse
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.backends.backend_pdf as backpdf
from  matplotlib import pyplot as plt
import pylab
import glob

#import uproot3
#import uproot
import time
import h5py

gpus = tf.config.experimental.list_physical_devices('GPU')
tf.config.experimental.set_memory_growth(gpus[0], True)

#################################################################################################################################################################################################################################################################################
##
##     USAGE
##  
##   standard workflow: 
##   1) python DeepCore.py --training                            #possibly on GPU, in this case the full training sample (hardcoded in the script) will be used
##   1.5) python DeepCore.py --training --continueTraining       #(step not mandatory) possibly on GPU, continue the training from the previously produced weights. The starting epochs and the input weights must be modified in the code
##   2) python DeepCore.py --predict --input INPUTNAME.root      #prediction on the "INPUTNAME.root" sample using the previously done training
##   3) python DeepCore.py --output --input INPUTNAME.root       #production of the validation rootfile using the previously produced prediction. needed ROOT. 
##  
##   all-in-one workflow (NOT recommended): local input training,  prediction and output validation on the same sample. needed ROOT.
##   python DeepCore.py --input INPUTNAME.root  --training --predict --output
##
##   several additional validation options are present, see in the Parser for full description.
################################################################################################################################################################################################################################################################################


parser = argparse.ArgumentParser(description="DeepCore NN training and prediction-test script")
parser.add_argument('--training',               dest='Training',                action='store_const',   const=True, default=False,           help='do the training of NN, if --input is empty used hardcoded sample')
parser.add_argument('--predict',                dest='Predict',                 action='store_const',   const=True, default=False,           help='do the prediction of NN, if without --training hardcoded weights are used')
parser.add_argument('--output',                 dest='Output',                  action='store_const',   const=True, default=False,           help='produce the output root file. NB: do not use on GPU (needed ROOT)')
parser.add_argument('--input',                  dest='Input',                   action='store',                     default='',  type=str,   help='name of the local input file, if missing using large size sample (hardcoded)')
parser.add_argument('--continueTraining',       dest='continueTraining',        action='store_const',   const=True, default=False,           help='continue the training from a previous step, start epoch hardcoded')
parser.add_argument('--onData',                 dest='onData',                  action='store_const',   const=True, default=False,           help='running on data (without the target, to check performance)')
parser.add_argument('--drawOnly',               dest='drawOnly',                action='store_const',   const=True, default=False,           help='draw in output info of input/target without prediction (to check the input features)')
parser.add_argument('--deb1ev',                 dest='deb1ev',                  action='store_const',   const=True, default=False,           help='debug on a single event')
parser.add_argument('--checkSample',            dest='checkSample',             action='store_const',   const=True, default=False,           help='check for NAN in the sample before training (very time consuming, only if strongly needed!)')
parser.add_argument('--averageValueTest',       dest='averageValueTest',        action='store_const',   const=True, default=False,           help='evaluation and print of average ADC count of input and 1-values present on the input (non required in standard workflow, only as extra validation)')
parser.add_argument('--testSampleBuild',        dest='testSampleBuild',         action='store_const',   const=True, default=False,           help='building a local test sample, useful to validation if is not present')
parser.add_argument('--extraValidation',        dest='extraValidation',         action='store_const',   const=True, default=False,           help='extra validation plot during training (very time consuming callback!)')
parser.add_argument('--rgb',                    dest='rgb',                     action='store_const',   const=True, default=False,           help='RGB color scheme plots (used in all the presented results')

## Adding new parser options
## passing number of epochs for training from command line rather than hard code
parser.add_argument('--epochs',                  dest='Epochs',    action='store',                     default=0,  type=int,   help=' Number of epochs to use for training')
## passing weight file from which to continue training from command line rather than hard code
parser.add_argument('--weights',                  dest='Weights',    action='store',                     default='',  type=str,   help='name of the local weight file, if missing use hardcoded one')
## passing epoch form which previous weight file stopped at so epoch numbering is correct
parser.add_argument('--epochsstart',                  dest='EpochsStart',    action='store',                     default=0,  type=int,   help=' Number of epochs to use for training')
## passing csv file which contains loss plots values from past trainings so the loss plots can include all epochs, not just the ones from this training
parser.add_argument('--csv',                          dest='Csv',            action='store',                     default='',  type=str,   help='name of the csv file')

args = parser.parse_args()

OUTPUT = args.Output
TRAIN = args.Training
PREDICT = args.Predict
input_name = args.Input
CONTINUE_TRAINING = args.continueTraining
ON_DATA = args.onData
DRAW_ONLY = args.drawOnly
DEB1EV = args.deb1ev
CHECK_SAMPLE = args.checkSample
AVERAGE_VALUES_TEST = args.averageValueTest
TEST_SAMPLE_BUILD = args.testSampleBuild
EXTRA_VALIDATION = args.extraValidation
RGB = args.rgb

## new args
EPOCHS_USED = args.Epochs
WEIGHTS_CONTINUE = args.Weights
EPOCHS_CONTINUE =args.EpochsStart
CSV_LOAD = args.Csv
#------------------------------------------------------------------------------------------#
#----------------------------- INTERNAL CONFIGURATION PARAMETERS --------------------------#
#------------------------------------------------------------------------------------------#

if input_name != '' :
    LOCAL_INPUT = True   #use the local input, "input_name"
else :
    LOCAL_INPUT = False #use the large sample, hardcoded below

#general configuration 
jetNum=0# number of jets in the input. will be filled with local input information
jetNum_validation = 0# number of jets in the input. will be filled with local input information
jetDim=30 #dimension of window on the pixed detector layer (cannot be changed without chaning the training sample)
overlapNum =3 #numer of overlap considered (cannot be changed without chaning the training sample)
layNum = 4 ## 4 for barrel, for endcap use layNum = 7 #4 barrel+3 endcap. the numeration is 1-4 for barrel, 5-7 for endcap (cannot be changed without chaning the training sample).
parNum=5 #number of track parameters (cannot be changed without chaning the training sample)
_Epsilon = 1e-7 #value needed for the loss functione valuation
inputModuleName= "DeepCoreNtuplizerTest" ## demo" ##"DeepCoreNtuplizerTest"
inputTreeName= "DeepCoreNtuplizerTree" ##"NNClustSeedInputSimHitTree" ##"DeepCoreNtuplizerTree"
# inputModuleName="demo" #2017 ntuples have this name
# inputTreeName="NNClustSeedInputSimHitTree" #2017 ntuples have this name

# traing parameter configuration
batch_size = 64 # Batch size for training.
#batch_size = 1 # Batch size for training.
## changed to use number of epochs provided by command line, otehrwise use hardcoded number
if EPOCHS_USED:
  epochs = EPOCHS_USED
else:
  epochs = 2 # Number of epochs to train for.
if EPOCHS_CONTINUE:
  start_epoch = EPOCHS_CONTINUE
else:
  start_epoch = 0 #starting epoch, to restart with proper numbering used when CONTINUE_TRAINING=True
valSplit=0.2 # fraction of input used for validation
prob_thr =0.85 # threshold to identfy good prediciton (see DeepCore documentation to details)

#plotting configuration
numPrint =5 #number of event saved in the root file
outEvent= 30 #complete plots for this event only

if TEST_SAMPLE_BUILD :
    jetNum_test=50
    input_test = np.zeros(shape=(jetNum_test, jetDim,jetDim,layNum)) #jetMap
    target_test = np.zeros(shape=(jetNum_test,jetDim, jetDim,overlapNum,parNum+1))#+1
    target_prob_test = np.zeros(shape=(jetNum_test,jetDim,jetDim,overlapNum))
    input_jeta_test = np.zeros(shape=(jetNum_test))
    input_jpt_test = np.zeros(shape=(jetNum_test))

if EXTRA_VALIDATION :
    efficiency_4 = np.zeros(epochs) #probably it can be removed (and also next lines)
    fake_rate_4 = np.zeros(epochs)
    efficiency_8 =  np.zeros(epochs)
    fake_rate_8 = np.zeros(epochs)




#--------------------------------------------------------------------------#
#------------------------- FUNCTIONS AND CLASSES --------------------------#
#--------------------------------------------------------------------------#

#Used in EXTRA_VALIDATION
#produces:
# 1) the residuals per epochs, 
# 2) homemade chi2 estimation between target and prediction
# 3) an efficiency and fake-rate estimation based on the chi2
class validationCall(Callback) : 
    def on_epoch_end(self,epoch, logs={}) :
        [call_par, call_prob] = self.model.predict([input_,input_jeta,input_jpt])
        call_prob = call_prob[:,:,:,:,:-1]

        for par in range(parNum) :
            bins = []# np.zeros(shape=(int(jetNum*valSplit)))
            nbin =0
            for j in range (int(jetNum*valSplit)) :
                j_eff = j+int(jetNum*(1-valSplit))
                for x in range(jetDim) :
                    for y in range(jetDim) :
                        for trk in range(overlapNum) :
                             if target_prob[j_eff][x][y][trk][0] == 1 :
                                if(par!=4) :
                                    bins.append((call_par[j_eff][x][y][trk][par] - target_[j_eff][x][y][trk][par])*0.01)
                                else :
                                     bins.append((call_par[j_eff][x][y][trk][par] - target_[j_eff][x][y][trk][par])/target_[j_eff][x][y][trk][par])  #relative
                                nbin = nbin+1

            plt.figure()
            pylab.hist(bins,100, facecolor='green', alpha=0.75)
            pylab.title('parNum error distribution_ep{EPOCH}_par{PAR}'.format(PAR=par,EPOCH=epoch))
            pylab.ylabel('entries')
            pylab.xlabel('parNum error')
            plt.grid(True)
            # pylab.savefig("parameter_error_{EPOCH}_{PAR}.pdf".format(PAR=par,EPOCH=epoch))
            pdf_par.savefig()

        N_eff_4 = 0
        N_eff_8 = 0
        N_fake_4 =0
        N_fake_8 = 0
        genTrackNum=3
        N_tot_eff = jetNum*valSplit*genTrackNum
        N_tot_fake = 0
        layDist=3
        for j in range (int(jetNum*valSplit)) :
            j_eff = j+int(jetNum*(1-valSplit))
            for x in range(jetDim) :
                for y in range(jetDim) :
                    for trk in range(overlapNum) :
                        if target_prob[j_eff][x][y][trk][0]==1 :
                            chi2x = (call_par[j_eff][x][y][trk][0] - target_[j_eff][x][y][trk][0])**2
                            chi2y = (call_par[j_eff][x][y][trk][1] - target_[j_eff][x][y][trk][1])**2
                            chi2xt = (call_par[j_eff][x][y][trk][2] - target_[j_eff][x][y][trk][2])**2 / math.atan(2/float(layDist*3))
                            chi2yt = (call_par[j_eff][x][y][trk][3] - target_[j_eff][x][y][trk][3])**2 / math.atan(2/float(layDist*3))
                            chi2 = chi2x+chi2y+chi2xt+chi2yt
                            if chi2<=4  and call_prob[j_eff][x][y][trk]>prob_thr:
                                N_eff_4 = N_eff_4 +1
                            if chi2<=8  and call_prob[j_eff][x][y][trk]>prob_thr:
                                N_eff_8 = N_eff_8 +1
                        if call_prob[j_eff][x][y][trk] > prob_thr :
                            N_tot_fake = N_tot_fake +1
                            chi2x = (call_par[j_eff][x][y][trk][0] - target_[j_eff][x][y][trk][0])**2
                            chi2y = (call_par[j_eff][x][y][trk][1] - target_[j_eff][x][y][trk][1])**2
                            chi2xt = (call_par[j_eff][x][y][trk][2] - target_[j_eff][x][y][trk][2])**2 / math.atan(2/float(layDist*3))
                            chi2yt = (call_par[j_eff][x][y][trk][3] - target_[j_eff][x][y][trk][3])**2 / math.atan(2/float(layDist*3))
                            chi2 = chi2x+chi2y+chi2xt+chi2yt
                            if chi2>=4  and target_prob[j_eff][x][y][trk][0]==1:
                                N_fake_4 = N_fake_4 +1
                            if chi2>=8  and target_prob[j_eff][x][y][trk][0]==1:
                                N_fake_8 = N_fake_8 +1

        efficiency_4[epoch] = N_eff_4/N_tot_eff
        if N_tot_fake == 0 :
            fake_rate_4[epoch] = 1
        else :
           fake_rate_4[epoch] = N_fake_4/N_tot_fake

        efficiency_8[epoch] = N_eff_8/N_tot_eff
        if N_tot_fake == 0  :
            fake_rate_8[epoch] = 1
        else :
           fake_rate_8[epoch] = N_fake_8/N_tot_fake

#callback to have additional trained model every 10 epochs
class wHistory(keras.callbacks.Callback):
   def on_epoch_end(self, epoch, logs={}):
       if epoch % 10 == 0 :
               self.model.save("trained"+str(epoch+0)+".h5")
wH = wHistory()

#callback to have the weight saved every batch
class WeightsSaver(Callback):
    def __init__(self, N):
        self.N = N
        self.batch = 0

    def on_batch_end(self, batch, logs={}):
        if self.batch % self.N == 0:
            name = 'weights%08d.h5' % self.batch
            self.model.save_weights(name)
        self.batch += 1

#used in EXTRA_VALIDATION to have additional log info
class NBatchLogger(Callback):
    """
    A Logger that log average performance per `display` steps.
    """
    def __init__(self, display):
        self.step = 0
        self.display = display
        self.metric_cache = {}

    def on_batch_end(self, batch, logs={}):
        self.step += 1
        for k in self.params['metrics']:
            if k in logs:
                self.metric_cache[k] = self.metric_cache.get(k, 0) + logs[k]
        if self.step % self.display == 0:
            metrics_log = ''
            for (k, v) in self.metric_cache.items():
                val = v / self.display
                if abs(val) > 1e-3:
                    metrics_log += ' - %s: %.4f' % (k, val)
                else:
                    metrics_log += ' - %s: %.4e' % (k, val)
            print('step: {}/{} ... {}'.format(self.step,
                                          self.params['steps'],
                                          metrics_log))
            self.metric_cache.clear()


#used in the losses
def _to_tensor(x, dtype):
    return ops.convert_to_tensor(x, dtype=dtype)

#used in the losses
def epsilon():
    return _Epsilon

#loss function for probability, used in the first part of the training
def loss_ROI_crossentropy(target, output):
    epsilon_ = _to_tensor(keras.backend.epsilon(), output.dtype.base_dtype)
    output = clip_ops.clip_by_value(output, epsilon_, 1 - epsilon_)
    wei = target[:,:,:,:,-1:]
    target = target[:,:,:,:,:-1]
    output = output[:,:,:,:,:-1]
    output = math_ops.log(output / (1 - output))
    retval = nn.weighted_cross_entropy_with_logits(labels=target, logits=output, pos_weight=10)#900=works #2900=200x200, 125=30x30
    retval = retval*wei
    return tf.reduce_sum(retval, axis=None)/(tf.reduce_sum(wei,axis=None)+0.00001) #0.00001 needed to avoid numeric issue

#loss function for probability, used in the last part of the training (difference: non-zero weight to pixel far from crossing point)
def loss_ROIsoft_crossentropy(target, output):
    epsilon_ = _to_tensor(keras.backend.epsilon(), output.dtype.base_dtype)
    output = clip_ops.clip_by_value(output, epsilon_, 1 - epsilon_)
    wei = target[:,:,:,:,-1:]
    target = target[:,:,:,:,:-1]
    output = output[:,:,:,:,:-1]
    output = math_ops.log(output / (1 - output))
    retval = nn.weighted_cross_entropy_with_logits(labels=target, logits=output, pos_weight=10)#900=works #2900=200x200, 125=30x30
    retval = retval*(wei+0.01) # here the difference
    ## ROIsoft: does not work since denominator goes to 0 sometimes 
    ## return tf.reduce_sum(retval, axis=None)/(tf.reduce_sum(wei,axis=None))
    ## ROIsoft fix 1
    ## return tf.reduce_sum(retval, axis=None)/(tf.reduce_sum(wei,axis=None)+0.00001)
    ## ROIsoft fix 2
    return tf.reduce_sum(retval,axis=None)/(tf.reduce_sum((wei+0.01),axis=None))

#loss for track parameter
def loss_mse_select_clipped(y_true, y_pred) :
    wei = y_true[:,:,:,:,-1:]
    pred = y_pred[:,:,:,:,:-1]
    true =  y_true[:,:,:,:,:-1]
    inv_sd = tf.constant([1/0.404, 1/0.478, 1/1.9, 1/2, 1/150], dtype=tf.float32) # inverse standard deviation of each TP
    mean = tf.constant([0, 0, 0, 0, 95], dtype=tf.float32) # mean of each TP
   # Standardization of target and predicted TPs
    pred = tf.subtract(pred, mean)* inv_sd
    true = tf.subtract(true,mean)*inv_sd
    out =K.square(tf.clip_by_value(pred-true,-5,5))*wei  # Clipping at +/-5 sigmas
    return tf.reduce_sum(out, axis=None)/(tf.reduce_sum(wei,axis=None)*5+0.00001) #5=parNum

# Generator used to load all the input file in the LOCAL_INPUT=False workflow
## Changed uproot to uproot3 in order to use central sample

#OUTDATED! Doesn't run on all cycles
def Generator(files) :
     while 1:
        print("entering while loop")
        for f in files :
            import uproot3
            tfile = uproot3.open(f)
            tree = tfile[inputModuleName][inputTreeName]
            input_ = tree.array("cluster_measured")
            input_jeta = tree.array("jet_eta")
            input_jpt = tree.array("jet_pt")
            target_ = tree.array("trackPar")
            target_prob = tree.array("trackProb")

            wei = target_[:,:,:,:,-1:]
            nev = len(target_prob)
            target_prob = np.reshape(target_prob, (nev,jetDim,jetDim,overlapNum,1))
            target_prob = concatenatenp([target_prob,wei],axis=4)
            print(len(input_jeta),batch_size, len(input_jeta)/batch_size)
            for k in range(int(len(input_jeta)/batch_size)) :
                yield [input_[batch_size*(k):batch_size*(k+1)],input_jeta[batch_size*(k):batch_size*(k+1)],input_jpt[batch_size*(k):batch_size*(k+1)]], [target_[batch_size*(k):batch_size*(k+1)],target_prob[batch_size*(k):batch_size*(k+1)]]

#runs on cycles 1-8, automatic batching, uproot4
def Generator2(filepath,batch_size=0,count=False):
    if count:
        branches = ["jet_eta"]
        batch_size = 1000
    else:
        branches = ["cluster_measured","jet_eta","jet_pt","trackPar","trackProb"]

    while 1:
        for cycle in range(1,9):
           # print(cycle)
            for chunk in uproot.iterate("{}:{}/{};{}".format(filepath,inputModuleName,inputTreeName,str(cycle)),branches,step_size=batch_size,library="np"):
                if count:
                    yield chunk['jet_eta'].shape[0]
                else:
                    nev = len(chunk["trackProb"])

                    target_prob = np.reshape(chunk["trackProb"], (nev,jetDim,jetDim,overlapNum,1))

                    target_prob = concatenatenp([target_prob,chunk["trackPar"][:,:,:,:,-1:]],axis=4)
                    #zero_elements = target_prob[:,:,:,:,-1]==0 #build an array that's True for every 0-valued entry
                    #target_prob[:,:,:,:,-1]=1.0/target_prob[:,:,:,:,-1] #invert everything, which will send all 0 pt entries to inf
                    #target_prob[:,:,:,:,-1][zero_elements] = 0 #reassign the inf values back to 0
                    
                    ## debug
                    ##pdb.set_trace()
                    yield [chunk['cluster_measured'][:,:,:,0:layNum],chunk["jet_eta"],chunk["jet_pt"]],[chunk["trackPar"],target_prob]
        if count:
            break


class HDF5Generator:
    def __init__(self,fname,batchsize):
        self.fname=fname
        self.batchsize=batchsize
    def __call__(self):
        with h5py.File(self.fname,'r',libver='latest') as f:
            batchsize=self.batchsize
            nbatches = int(f['jet_eta'].shape[0]/batchsize)
            indices=np.arange(nbatches)
            print("Initialize HDF5 Generator")
            while True:
                np.random.shuffle(indices)
                for index in indices:
                    ind=index*batch_size
                    batch=((f["cluster_measured"][ind:ind+batchsize],f["jet_eta"][ind:ind+batchsize],f['jet_pt'][ind:ind+batchsize]),(f['trackPar'][ind:ind+batchsize],f['trackProb'][ind:ind+batchsize]))

                    for i in range(batchsize):
                        #yield ((f["cluster_measured"][i],f["jet_eta"][i],f['jet_pt'][i]),(f['trackPar'][i],f['trackProb'][i]))
                        yield ((batch[0][0][i],batch[0][1][i],batch[0][2][i]),(batch[1][0][i],batch[1][1][i]))
    def nbatches(self):
        with h5py.File(self.fname,'r') as f:
            nbatches = int(f['jet_eta'].shape[0]/self.batchsize)
            return nbatches
    def nrows(self):
        with h5py.File(self.fname,'r') as f:
            nbatches = f['jet_eta'].shape[0]
            return nbatches

class HDF5GeneratorN:
    #yield from subset i/N (for interleave)
    def __init__(self,fname,batchsize,N):
        self.fname=fname
        self.batchsize=batchsize
        self.N=N #tot number of generators
    def __call__(self,i):
        self.i=i #generator index
        self.n_batch = self.nbatches()
        self.i_batch= int(self.n_batch*i/self.N)
        self.f_batch= int(self.n_batch*(i+1)/self.N)
        with h5py.File(self.fname,'r',libver='latest') as f:
            batchsize=self.batchsize
            indices=np.arange(self.i_batch,self.f_batch)
            print("Initialize HDF5 Generator")
            while True:
                np.random.shuffle(indices)
                for index in indices:
                    ind=index*batch_size
                    batch=((f["cluster_measured"][ind:ind+batchsize],f["jet_eta"][ind:ind+batchsize],f['jet_pt'][ind:ind+batchsize]),(f['trackPar'][ind:ind+batchsize],f['trackProb'][ind:ind+batchsize]))

                    for i in range(batchsize):
                        yield ((batch[0][0][i],batch[0][1][i],batch[0][2][i]),(batch[1][0][i],batch[1][1][i]))
    def nbatches(self):
        with h5py.File(self.fname,'r') as f:
            nbatches = int(f['jet_eta'].shape[0]/self.batchsize)
            return nbatches
    def nrows(self):
        with h5py.File(self.fname,'r') as f:
            return f['jet_eta'].shape[0]


# linear propagation to the 4 barrel layers, with plotting purpose only
def prop_on_layer(x1,y1,eta,phi,eta_jet,lay) :

    theta_jet = 2*math.atan(math.exp(-eta_jet))
    eta = eta+eta_jet
    theta = 2*math.atan(math.exp(-eta))

    if(lay==0) :
        dist=3-6.8
    if(lay==1) :
        dist=6.8-6.8
    if(lay==2) :
        dist=10.2-6.8
    if(lay==3) :
        dist=16-6.8
    distx=dist/0.01
    disty=dist/0.015

    y_out = disty*math.sin(theta-theta_jet)/(math.sin(theta_jet)*math.sin(theta))+y1
    x_out = distx*math.tan(-phi)+x1

    return (x_out,y_out)
    
# function called with  TEST_SAMPLE_BUILD=True
def test_sample_creation(input_,input_jeta,input_jpt,target_,target_prob) :
    print("testing sample creation: ...")
    for jj in range (jetNum_test) :
        j = jj+(int(len(input_))-jetNum_test-5)
        input_jeta_test[jj] = input_jeta[j]
        input_jpt_test[jj] = input_jpt[j]
        for x in range(jetDim) :
            for y in range(jetDim) :
                for par in range(parNum+1) :
                    if(par<4) :
                        input_test[jj][x][y][par] = input_[j][x][y][par]
                    for trk in range(overlapNum) :
                        target_test[jj][x][y][trk][par] = target_[j][x][y][trk][par]
                        target_prob_test[jj][x][y][trk] = target_prob[j][x][y][trk]
    print("... save ...")
    np.savez("DeepCore_ev{ev}_test".format(ev=jetNum_test), input_=input_test, input_jeta=input_jeta_test, input_jpt=input_jpt_test, target_=target_test, target_prob =target_prob_test)
    print("..completed")

# function called with  AVERAGE_VALUES_TEST=True
def average_1_eval(input_, target_prob) :
    aver1=0
    print("evaluation of the number of 1, input len=",int(len(input_)))
    for j in range (int(len(input_))) :
        averjet = 0
        aver0jet = 0
        for x in range(jetDim) :
            for y in range(jetDim) :
                    if(target_prob[j][x][y][0][1]) :
                        aver0jet = aver0jet+1
                        if(target_prob[j][x][y][0][0]==1) :
                            averjet = averjet+1
        if(aver0jet!=0) :
            averjet = float(averjet)/float(aver0jet)
        else :
            averjet = 0
        aver1= aver1+averjet
    aver1 = float(aver1)/float(len(input_))
    print("average of the number of 1", aver1)
    print("Multiplicative factor to 1", 1/aver1)

# function called with  DEB1EV=True
def Deb1ev_sampleBuilding(input_,input_jeta,input_jpt,target_,target_prob) :
    print("Dev1ev ampleBuilding")
    input_= input_[1:2]
    input_jeta= input_jeta[1:2]
    input_jpt= input_jpt[1:2]
    target_= target_[1:2]
    target_prob= target_prob[1:2]

# function called with  AVERAGE_VALUES_TEST=True
def averageADC(input_) :  
    averADC=0
    norm = 0
    bins = []
    print("evaluation of averge ADC count")
    for j in range (int(len(input_))) :
        # averjet = 0
        for x in range(jetDim) :
            for y in range(jetDim) :
                for l in range(layNum) :
                    if(input_[j][x][y][l]!=0) :
                        averADC=averADC+input_[j][x][y][l]
                        bins.append(input_[j][x][y][l])
                        norm = norm +1
    averADC = float(averADC)/float(norm)
    occupancy = float(norm)/(float(jetDim*jetDim*layNum*int(len(input_))))
    print("average value of input=", averADC)
    print("average occupancy=", occupancy)

    plt.figure()
    pylab.hist(bins,100, facecolor='green')
    pylab.title('Non-zero ADC count distribution')
    pylab.ylabel('entries')
    pylab.xlabel('ADC count')
    plt.grid(True)
    pylab.savefig("ADC_count.pdf")  

# function called with  CHECK_SAMPLE=True
def check_sample(files_input,files_input_validation) :
    #------ check nan/inf in the sample -------------#
    print("checksample")
    print("number of  file=", len(files_input))
    for f in files_input :
            tfile = uproot.open(f)
            tree = tfile[inputModuleName][inputTreeName]
            input_ = tree.array("cluster_measured")
            input_jeta = tree.array("jet_eta")
            input_jpt = tree.array("jet_pt")
            target_ = tree.array("trackPar")
            target_prob = tree.array("trackProb")

            # weicheck = target_[:,:,:,:,-1:]
            # print("file target ",f," wei sum=", K.eval(tf.reduce_sum(weicheck,axis=None)))
            print("file input ",f,", NAN=",np.isnan(np.sum(input_)))
            print("file input ",f,", inf=",np.isinf(np.sum(input_)))
            print("file input jeta ",f,", NAN=",np.isnan(np.sum(input_jeta)))
            print("file input jeta ",f,", inf=",np.isinf(np.sum(input_jeta)))
            print("file input jpt ",f,", NAN=",np.isnan(np.sum(input_jpt)))
            print("file input jpt ",f,", inf=",np.isinf(np.sum(input_jpt)))
            print("file target ",f,", NAN=",np.isnan(np.sum(target_)))
            print("file target ",f,", inf=",np.isinf(np.sum(target_)))
            print("file target prob ",f,", NAN=",np.isnan(np.sum(target_prob)))
            print("file target prob ",f,", inf=",np.isinf(np.sum(target_prob)))
    for f in files_input_validation :
            tfile = uproot.open(f)
            tree = tfile[inputModuleName][inputTreeName]
            input_ = tree.array("cluster_measured")
            input_jeta = tree.array("jet_eta")
            input_jpt = tree.array("jet_pt")
            target_ = tree.array("trackPar")
            target_prob = tree.array("trackProb")

            # weicheck = target_[:,:,:,:,-1:]
            # print("file target ",f," wei sum=", K.eval(tf.reduce_sum(weicheck,axis=None)))
            print("file input ",f,", NAN=",np.isnan(np.sum(input_)))
            print("file input ",f,", inf=",np.isinf(np.sum(input_)))
            print("file input jeta ",f,", NAN=",np.isnan(np.sum(input_jeta)))
            print("file input jeta ",f,", inf=",np.isinf(np.sum(input_jeta)))
            print("file input jpt ",f,", NAN=",np.isnan(np.sum(input_jpt)))
            print("file input jpt ",f,", inf=",np.isinf(np.sum(input_jpt)))
            print("file target ",f,", NAN=",np.isnan(np.sum(target_)))
            print("file target ",f,", inf=",np.isinf(np.sum(target_)))
            print("file target prob ",f,", NAN=",np.isnan(np.sum(target_prob)))
            print("file target prob ",f,", inf=",np.isinf(np.sum(target_prob)))
            








#-----------------------------------------------------------------------------#
#----------------------------------INPUT -------------------------------------#
#-----------------------------------------------------------------------------#

if(LOCAL_INPUT) : #loaded the local input
    print("WARNING: using local data (also for training!)")
    print("loading data: start")

    tfile = uproot3.open(input_name)
    tree = tfile[inputModuleName][inputTreeName]
    tree = tfile[inputModuleName][inputTreeName]
    ##print(tree)
    input_ = tree.array("cluster_measured")
    input_jeta = tree.array("jet_eta")
    input_jpt = tree.array("jet_pt")
    if(not ON_DATA):
        target_ = tree.array("trackPar")
        target_prob = tree.array("trackProb")
        wei = target_[:,:,:,:,-1:]
        nev = len(target_prob)
        target_prob = np.reshape(target_prob, (nev,jetDim,jetDim,overlapNum,1))
        target_prob = concatenatenp([target_prob,wei],axis=4)

    print("loading data: completed")

else :  #loaded the central input
    #---------------- central input  ----------------#

    #HDF5
    trainfile="/content/data/train.hdf5"
    valfile="/content/data/val.hdf5"
    #trainfile="/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/train.hdf5"
    #valfile="/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/val.hdf5"

    #barrel full stat
    ## files=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8//NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0000/ntuple*.root') + glob.glob('/gpfs/ddn/srm/cm
    ## files=glob.glob('/storage/local/data1/gpuscratch/hichemb/XTraining0211/DeepCoreTrainingSample.root')
    #files=glob.glob('/storage/local/data1/gpuscratch/hichemb/Training0217/TrainingSamples/training/DeepCoreTrainingSample*.root')
    #files_validation=glob.glob('/storage/local/data1/gpuscratch/hichemb/Training0217/TrainingSamples/validation/DeepCoreTrainingSample*.root')
    #Generator2 approach
    #trainingpath = "/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/TrainingSamples/training/DeepCoreTrainingSample_*.root"
    #validationpath = "/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/TrainingSamples/validation/DeepCoreTrainingSample_*.root"
    #validationpath = "/storage/local/data1/gpuscratch/hichemb/DeepCore_git/DeepCore_Training/TrainingSamples/validation/DeepCoreTrainingSample_*.root"
    #GPU3 training/validation files
    #trainingpath = "/storage/local/data1/gpuscratch/njh/Training0217/training/DeepCoreTrainingSample_*.root:DeepCoreNtuplizerTest/DeepCoreNtuplizerTree;"
    #validationpath = "/storage/local/data1/gpuscratch/njh/Training0217/validation/DeepCoreTrainingSample_*.root:DeepCoreNtuplizerTest/DeepCoreNtuplizerTree;"

    #files_validation=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8//NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0004/ntuple_simHit_1LayClustPt_cutPt_46*.root')+glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8//NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0004/ntuple_simHit_1LayClustPt_cutPt_47*.root')+glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8//NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0004/ntuple_simHit_1LayClustPt_cutPt_48*.root')+glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8//NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0004/ntuple_simHit_1LayClustPt_cutPt_49*.root')

    #barrel small stat
    # files=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8/NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0000/ntuple_simHit_1LayClustPt_cutPt_9*.root')
    # files_validation=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/QCD_Pt_1800to2400_TuneCUETP8M1_13TeV_pythia8/NNClustSeedInputSimHit_1LayClustPt_cutPt/190216_214452/0000/ntuple_simHit_1LayClustPt_cutPt_9*.root')

    #Endcap (pt cut 500GeV, 30x30) full stat
    # files=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0000/nuple_ntuple_EC_centralEgun_pt500cut_*.root')+ glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0002/nuple_ntuple_EC_centralEgun_pt500cut_*.root')+ glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0003/nuple_ntuple_EC_centralEgun_pt500cut_*.root')+ glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0004/nuple_ntuple_EC_centralEgun_pt500cut_*.root')
    # files_validation = glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0001/nuple_ntuple_EC_centralEgun_pt500cut_*.root')

    # Endcap small stat
    # files=glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0000/ntuple_EC_centralEgun_pt500cut_*.root')
    # files_validation = glob.glob('/gpfs/ddn/srm/cms/store/user/vbertacc/NNClustSeedInputSimHit/UBGGun_E-1000to7000_Eta-1p2to2p1_13TeV_pythia8/NNClustSeedInputSimHit_EC_centralEgun_pt500cut/200603_153129/0001/ntuple_EC_centralEgun_pt500cut_1*.root')





#-----------------------------------------------------------------------------------------#
#----------------------------------- extra preliminary tests -----------------------------#
#-----------------------------------------------------------------------------------------#

# everything False in default workflow
if LOCAL_INPUT :
    if TEST_SAMPLE_BUILD :
        test_sample_creation(input_,input_jeta,input_jpt,target_,target_prob)
    if AVERAGE_VALUES_TEST :
        average_1_eval(input_, target_prob)
        averageADC(input_)
    if DEB1EV :
        Deb1ev_sampleBuilding(input_,input_jeta,input_jpt,target_,target_prob)
elif CHECK_SAMPLE:
    check_sample(files_,files_validation)




#----------------------------------------------------------------------------------------#
#-----------------------------------------KERAS MODEL -----------------------------------#
#----------------------------------------------------------------------------------------#

# Training info for barrel, 2017 conditions (manual monitor and switch. Must be automatized).    
# Epochs 0-11    ---> 200k ev, LR=0.0002,     loss_ROI_crossentropy
# Epochs 11-40   ---> 200k ev, LR=0.0001,     loss_ROI_crossentropy
# Epochs 40-191  ---> 200k ev, LR=0.00007,    loss_ROI_crossentropy
# Epochs 191-200 ---> 200k ev, LR=0.00007,    loss_ROIsoft_crossentropy
# Epochs 200-233 ---> 200k ev, LR= 0.000001,  loss_ROIsoft_crossentropy
# Epochs 233-239 ---> 22M ev,  LR= 0.000001,  loss_ROIsoft_crossentropy
# Epochs 239-246 ---> 22M ev,  LR =0.0000001, loss_ROIsoft_crossentropy, epochs of 1M ev--> steps/20
# Epochs 246-252 ---> 22M ev,  LR =0.00000001,loss_ROIsoft_crossentropy, epochs of 1M ev--> steps/20, batch_size=64 (experimental, never used in CMSSW)

if TRAIN or PREDICT :

    from keras.layers import AlphaDropout

    NNinputs_jeta = Input(shape=(1,))
    NNinputs_jpt = Input(shape=(1,))
    NNinputsJet = concatenate([NNinputs_jeta,NNinputs_jpt])
    jetReshaped = Reshape((1,1,2))(NNinputsJet)
    jetUps = UpSampling2D(size=(jetDim,jetDim), data_format="channels_last")(jetReshaped)
    print("jetUps=", jetUps.shape)
    NNinputs = Input(shape=(jetDim,jetDim,layNum))
    print("NNinputs=", NNinputs.shape)
    ComplInput = concatenate([NNinputs,jetUps],axis=3)
    print("ComplInput=", ComplInput.shape)

# Run 2 Architecture
#    conv30_9 = Conv2D(50,7, data_format="channels_last", input_shape=(jetDim,jetDim,layNum+2), activation='relu',padding="same")(ComplInput)
#    conv30_7 = Conv2D(20,5, data_format="channels_last", activation='relu',padding="same")(conv30_9)
#    conv30_5 = Conv2D(20,5, data_format="channels_last", activation='relu',padding="same")(conv30_7)#
#    conv20_5 = Conv2D(18,5, data_format="channels_last", activation='relu',padding="same")(conv30_5)
#    conv15_5 = Conv2D(18,3, data_format="channels_last", activation='relu',padding="same")(conv20_5)

#    conv15_3_1 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_5)
#    conv15_3_2 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_1)
#    conv15_3_3 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_2) #(12,3)
#    conv15_3 = Conv2D(18,3, data_format="channels_last",padding="same")(conv15_3_3) #(12,3)
    # T1023 architecture difference (last layer has 1x1 filter instead of 3x3
    # conv15_3 = Conv2D(18,1, data_format="channels_last",padding="same")(conv15_1_1) #(12,1)
#    reshaped = Reshape((jetDim,jetDim,overlapNum,parNum+1))(conv15_3)

#    conv12_3_1 = Conv2D(18,3, data_format="channels_last", activation='relu', padding="same")(conv15_5)  #new
#    conv1_3_2 = Conv2D(9,3, data_format="channels_last", activation='relu', padding="same")(conv12_3_1) #drop7lb   #new
#    conv1_3_3 = Conv2D(7,3, data_format="channels_last", activation='relu',padding="same")(conv1_3_2) #new
#    conv1_3_1 = Conv2D(6,3, data_format="channels_last", activation='sigmoid', padding="same")(conv1_3_3)
#    reshaped_prob = Reshape((jetDim,jetDim,overlapNum,2))(conv1_3_1)
#############################################################################################################################

 # DeepCore 2.0/2.1 Architecture
#    conv30_9 = Conv2D(50,7, data_format="channels_last", input_shape=(jetDim,jetDim,layNum+2), activation='relu',padding="same")(ComplInput)
#    conv30_7 = Conv2D(40,5, data_format="channels_last", activation='relu',padding="same")(conv30_9)
#    conv30_5 = Conv2D(40,5, data_format="channels_last", activation='relu',padding="same")(conv30_7)#
#    conv20_5 = Conv2D(30,5, data_format="channels_last", activation='relu',padding="same")(conv30_5)
#    conv15_5 = Conv2D(30,3, data_format="channels_last", activation='relu',padding="same")(conv20_5)

#    conv15_3_1 = Conv2D(30,3, data_format="channels_last",activation='relu', padding="same")(conv15_5)
#    conv15_3_2 = Conv2D(30,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_1)
#    conv15_3_3 = Conv2D(30,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_2) #(12,3)
#    conv15_3 = Conv2D(18,3, data_format="channels_last",padding="same")(conv15_3_3) #(12,3)
#    reshaped = Reshape((jetDim,jetDim,overlapNum,parNum+1))(conv15_3)

#    conv12_3_1 = Conv2D(30,3, data_format="channels_last", activation='relu', padding="same")(conv15_5)  #new
#    conv1_3_2 = Conv2D(25,3, data_format="channels_last", activation='relu', padding="same")(conv12_3_1) #drop7lb   #new
#    conv1_3_3 = Conv2D(20,3, data_format="channels_last", activation='relu',padding="same")(conv1_3_2) #new
#    conv1_3_1 = Conv2D(6,3, data_format="channels_last", activation='sigmoid', padding="same")(conv1_3_3)
#    reshaped_prob = Reshape((jetDim,jetDim,overlapNum,2))(conv1_3_1)
#######################################################################################################################
     # DeepCore 2.2 Architecture
    conv30_9 = Conv2D(50,7, data_format="channels_last", input_shape=(jetDim,jetDim,layNum+2), activation='relu',padding="same")(ComplInput)
    conv30_7 = Conv2D(40,5, data_format="channels_last", activation='relu',padding="same")(conv30_9)
    conv30_5 = Conv2D(40,5, data_format="channels_last", activation='relu',padding="same")(conv30_7)#
    conv20_5 = Conv2D(30,5, data_format="channels_last", activation='relu',padding="same")(conv30_5)
    conv15_5 = Conv2D(30,3, data_format="channels_last", activation='relu',padding="same")(conv20_5)

    conv15_3_1 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_5)
    conv15_3_2 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_1)
    conv15_3_3 = Conv2D(18,3, data_format="channels_last",activation='relu', padding="same")(conv15_3_2) #(12,3)
    conv15_3 = Conv2D(18,3, data_format="channels_last",padding="same")(conv15_3_3) #(12,3)
    reshaped = Reshape((jetDim,jetDim,overlapNum,parNum+1))(conv15_3)

    conv12_3_1 = Conv2D(30,3, data_format="channels_last", activation='relu', padding="same")(conv15_5)  #new
    conv1_3_2 = Conv2D(30,3, data_format="channels_last", activation='relu', padding="same")(conv12_3_1) #drop7lb   #new
    conv1_3_3 = Conv2D(30,3, data_format="channels_last", activation='relu',padding="same")(conv1_3_2) #new
    conv1_3_1 = Conv2D(6,3, data_format="channels_last", activation='sigmoid', padding="same")(conv1_3_3)
    reshaped_prob = Reshape((jetDim,jetDim,overlapNum,2))(conv1_3_1)
#######################################################################################################################
    model = Model([NNinputs,NNinputs_jeta,NNinputs_jpt],[reshaped,reshaped_prob])
    
    # Made it easier to adjust learning rate
    #anubi = keras.optimizers.Adam(learning_rate=0.00001)#after epochs 252 (with septs/20 and batch_size 64)
    #Learning rate adjustments:
    # anubi = keras.optimizers.Adam(learning_rate=0.01)  #10-2
    #anubi = keras.optimizers.Adam(learning_rate=0.001)  #10-3
    #anubi = keras.optimizers.Adam(learning_rate=0.0001)  #10-4
    #anubi = keras.optimizers.Adam(learning_rate=0.00001)  #10-5
    anubi = keras.optimizers.Adam(learning_rate=0.000001)  #10-6
    # anubi = keras.optimizers.Adam(learning_rate=0.0000001)  #10-7
    # anubi = keras.optimizers.Adam(learning_rate=0.00000001)  #10-8
    
    # Loss function adjustments:
    # ROI
    #model.compile(optimizer=anubi, loss=[loss_mse_select_clipped,loss_ROI_crossentropy], loss_weights=[1,1]) #FOR EARLY TRAINING
    # ROIsoft
    model.compile(optimizer=anubi, loss=[loss_mse_select_clipped,loss_ROIsoft_crossentropy], loss_weights=[1,1]) #FOR LATE TRAINING



    model.summary()


#--------------------------------------------------------------------------------------------------------#
#-----------------------------------------NN TRAINING and PREDICITION -----------------------------------#
#--------------------------------------------------------------------------------------------------------#



#evaluation of number of events used 


if(LOCAL_INPUT) :
    tfile = uproot3.open(input_name)
    tree = tfile[inputModuleName][inputTreeName]
    input_jeta2 = tree.array("jet_eta")
    tot_events = len(input_jeta2)
    tot_events_validation=tot_events*valSplit
    tot_events=tot_events*(1-valSplit)
else :
    trainGenN = HDF5GeneratorN(trainfile,batch_size*4,1)
    valGenN = HDF5GeneratorN(trainfile,batch_size*4,1)
    tot_events = trainGenN.nrows()
    tot_events_validation = valGenN.nrows()
    print("number of rows (training) {}".format(tot_events))
    print("number of rows (validation) {}".format(tot_events_validation))
    
    #for batch in Generator2(trainingpath,count=True):
    #    tot_events += batch
    #for batch in Generator2(validationpath,count=True):
    #    tot_events_validation += batch


jetNum = tot_events
jetNum_validation = tot_events_validation
print("total number of events =", jetNum)
print("total number of events validation=", jetNum_validation)

## commented out since cant find val loss
checkpointer = ModelCheckpoint(filepath="weights.{epoch:02d}-{val_loss:.4f}.hdf5",verbose=1, save_weights_only=False)
#checkpointer= ModelCheckpoint(filepath="weights.{epoch:02d}.hdf5",verbose=1, save_weights_only=False)

if TRAIN :
    stepNum = jetNum/batch_size
    print("Number of Steps: {}".format(stepNum)) 
    if CONTINUE_TRAINING :
       ## Using weight file given from command line otherwise use hardcode weight file 
       if WEIGHTS_CONTINUE:
         model.load_weights(WEIGHTS_CONTINUE)
       else:
        #Barrel training (used in presentation, CMSSW PR...)
        model.load_weights('data/DeepCore_barrel_weights.246-0.87.hdf5')
        
        #EndCap training, last weights (not satisfactory, consider to restart)
        # model.load_weights('../data/DeepCore_ENDCAP_train_ep150.h5')
        
       # model.load_weights('DeepCore_train_ev{ev}_ep{ep}.h5'.format(ev=jetNum,ep=start_epoch))
    else : #restart training
        start_epoch = 0
    
    print("training: start")
    
    if LOCAL_INPUT :
        if DEB1EV :
            history  = model.fit([input_,input_jeta,input_jpt], [target_,target_prob],  batch_size=batch_size, epochs=epochs+start_epoch, verbose = 2,initial_epoch=start_epoch)
        elif EXTRA_VALIDATION :
            pdf_par = mpl.backends.backend_pdf.PdfPages("DeepCore_parameter_file_ep{Epoch}.pdf".format(Epoch=epochs+start_epoch))
            history  = model.fit([input_,input_jeta,input_jpt], [target_,target_prob],  batch_size=batch_size, epochs=epochs+start_epoch, verbose = 2, validation_split=valSplit,  initial_epoch=start_epoch, callbacks=[checkpointer, NBatchLogger(1),validationCall() ])
            pdf_par.close()
        else :
            history  = model.fit([input_,input_jeta,input_jpt], [target_,target_prob],  batch_size=batch_size, epochs=epochs+start_epoch, verbose = 2, validation_split=valSplit,  initial_epoch=start_epoch, callbacks=[checkpointer])            
    else : #full standard training
        ## Adjust step size between trainings: if step size = 1/20 then inverse_step_size = 20
        #history = model.fit_generator(generator=Generator(files),steps_per_epoch=stepNum, epochs=epochs+start_epoch, verbose = 2, max_queue_size=1, validation_data=Generator(files_validation),  validation_steps=jetNum_validation/batch_
        #history = model.fit(Generator2(trainingpath,batch_size),steps_per_epoch=int(stepNum/inverse_step_size),epochs=start_epoch+args.Epochs,verbose=2,max_queue_size=1,validation_data=Generator2(validationpath,batch_size),validation_steps=int(jetNum_validation/(val_inverse_step_size*batch_size)), initial_epoch=start_epoch, callbacks=[checkpointer])
        inverse_step_size=1
        val_inverse_step_size=1
            
        #HDF5 parallel
        trainfile="/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/train.hdf5"
        valfile="/storage/local/data1/gpuscratch/njh/DeepCore_data/DeepCore_Training/val.hdf5"
        precision=np.float16
        
        #use four copies of generator and interleave
        N=4
        trainGenN = HDF5GeneratorN(trainfile,batch_size*4,N)
        trainSteps=int(trainGenN.nrows()/batch_size)

        hdfTrain = tf.data.Dataset.range(N).interleave(
            lambda i: tf.data.Dataset.from_generator(
                trainGenN, args=(i,),
                output_signature=( (tf.TensorSpec(shape=(jetDim,jetDim,layNum), dtype=precision),
                    tf.TensorSpec(shape=(), dtype=precision),
                    tf.TensorSpec(shape=(), dtype=precision)),
                    (tf.TensorSpec(shape=(jetDim,jetDim,overlapNum,parNum+1), dtype=precision),
                    tf.TensorSpec(shape=(jetDim,jetDim,overlapNum,2), dtype=precision))
                )
            ), cycle_length=N, num_parallel_calls=4, deterministic=False #dangerous?
        ).batch(batch_size).apply(tf.data.experimental.copy_to_device("/gpu:0")).prefetch(tf.data.AUTOTUNE)
        
        valGenN = HDF5GeneratorN(valfile,batch_size*4,N)
        hdfVal = tf.data.Dataset.range(N).interleave(
            lambda i: tf.data.Dataset.from_generator(
                valGenN, args=(i,),
                output_signature=( (tf.TensorSpec(shape=(jetDim,jetDim,layNum), dtype=precision),
                    tf.TensorSpec(shape=(), dtype=precision),
                    tf.TensorSpec(shape=(), dtype=precision)),
                    (tf.TensorSpec(shape=(jetDim,jetDim,overlapNum,parNum+1), dtype=precision),
                    tf.TensorSpec(shape=(jetDim,jetDim,overlapNum,2), dtype=precision))
                )
            ), cycle_length=N, num_parallel_calls=4, deterministic=False
        ).batch(batch_size).apply(tf.data.experimental.copy_to_device("/gpu:0")).prefetch(tf.data.AUTOTUNE)
        valSteps=int(valGenN.nrows()/batch_size)

        start_time=time.time() 
        history = model.fit(hdfTrain,steps_per_epoch=trainSteps,epochs=start_epoch+args.Epochs,validation_data=hdfVal,validation_steps=valSteps, initial_epoch=start_epoch, callbacks=[checkpointer],verbose=2)
        stop_time=time.time() 
        
        print("Duration: {:.2f}".format(stop_time-start_time))
        print("done running; now save")
        
    model.save_weights('DeepCore_train_ev{ev}_ep{ep}.h5'.format(ev=jetNum, ep=epochs+start_epoch))
    model.save('DeepCore_model_ev{ev}_ep{ep}.h5'.format(ev=jetNum, ep=epochs+start_epoch))
    
    print("training: completed")


    #plot of the losses ---------------
    ## added start_epoch so loss file shows overall number of epochs
    pdf_loss = mpl.backends.backend_pdf.PdfPages("loss_file_ep{Epoch}_ev{ev}.pdf".format(Epoch=epochs+start_epoch,ev=jetNum))

    if(not DEB1EV) : 
      ## Saving values of loss plots in a csv file so we can make loss plots with all the epochs when continuing trainings
      epo = np.arange(start_epoch+1, epochs + start_epoch + 1)
      #print(epo)
      list_save = [epo, 
          history.history['loss'],
          history.history['val_loss'], 
          history.history['reshape_1_loss'],
          history.history['val_reshape_1_loss'],
          history.history['reshape_2_loss'],
          history.history['val_reshape_2_loss']]
      #print(list_save)
      arr = np.array(list_save)
      #print(arr.T)
      #print(history.history['loss'])
      #print(history.history['val_loss'])
      np.savetxt("loss_plots_{Epoch_i}_{Epoch_f}.csv".format(Epoch_i=start_epoch,Epoch_f=epochs+start_epoch),arr.T, delimiter = ",")
      #DF = pd.DataFrame(arr)
      #DF.to_csv("loss_plots_{Epoch_i}_{Epoch_f}.csv".format(Epoch_i=start_epoch,Epoch_f=epochs+start_epoch))

      if (CONTINUE_TRAINING and CSV_LOAD):
        csv_loss = pd.read_csv(CSV_LOAD)
        csv_loss_arr = csv_loss.to_numpy()
        #print(csv_loss_arr)
        arr_full = np.vstack((csv_loss_arr, arr.T))
        ## saving csv file with all loss values (current and previous trainings)
        np.savetxt("loss_plots_full_{Epoch_i}_{Epoch_f}.csv".format(Epoch_i=0,Epoch_f=epochs+start_epoch),arr_full, delimiter = ",")
        #print(arr_full)
        #print(arr_full[:,0])
        #print(arr_full[:,1])
      else:
        # if this is the first training then simply use the array defined earlier from history.history
        arr_full = arr.T
      
      # Plotting loss plots
      plt.figure(1000)
      plt.yscale('log')
      plt.plot(arr_full[:,0], arr_full[:,1])
      plt.plot(arr_full[:,0], arr_full[:,2])
      pylab.title('Model Loss')
      pylab.ylabel('Loss')
      pylab.xlabel('Epoch')
      plt.grid(True)
      pylab.legend(['train', 'validation'], loc='upper right')
      pdf_loss.savefig(1000, bbox_inches='tight')

      plt.figure(1001)
      plt.yscale('log')
      plt.plot(arr_full[:,0], arr_full[:,3])
      plt.plot(arr_full[:,0], arr_full[:,4])
      pylab.title('TP Loss')
      pylab.ylabel('Loss')
      pylab.xlabel('Epoch')
      plt.grid(True)
      pylab.legend(['train', 'validation'], loc='upper right')
      pdf_loss.savefig(1001, bbox_inches='tight')

      plt.figure(1002)
      plt.yscale('log')
      plt.plot(arr_full[:,0], arr_full[:,5])
      plt.plot(arr_full[:,0], arr_full[:,6])
      pylab.title('TCP Loss')
      pylab.ylabel('Loss')
      pylab.xlabel('Epoch')
      plt.grid(True)
      pylab.legend(['train', 'validation'], loc='upper right')
      pdf_loss.savefig(1002, bbox_inches='tight')

## Old plotting script
#        plt.figure(1000)
#        plt.yscale('log')
        ## pylab.plot(history.history['loss'])
        ## pylab.plot(history.history['val_loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['val_loss'])
#        pylab.title('model loss')
#        pylab.ylabel('loss')
#        pylab.xlabel('epoch')
#        plt.grid(True)
#        pylab.legend(['train', 'test'], loc='upper right')
#        pdf_loss.savefig(1000)

#        plt.figure(1001)
#        plt.yscale('log')
        ## adjusting x axis so it starts from the epoch number from last training in case we continue training
        ## pylab.plot(history.history['reshape_1_loss'])
        ## pylab.plot(history.history['val_reshape_1_loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['reshape_1_loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['val_reshape_1_loss'])
#        pylab.title('model loss (parameters)')
#        pylab.ylabel('loss')
#        pylab.xlabel('epoch')
#        plt.grid(True)
#        pylab.legend(['train', 'test'], loc='upper right')
#        pdf_loss.savefig(1001)

        ## Can't find reshape_3_loss in the training, only reshape 1 and
        ## 2 availabe so we changed reshape_2 -> reshape_1 and reshape_3 ->
        ## reshape_2
#        plt.figure(1002)
        # plt.yscale('log')
        ## pylab.plot(history.history['reshape_2_loss'])
        ## pylab.plot(history.history['val_reshape_2_loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['reshape_2_loss'])
#        plt.plot(range(start_epoch,epochs+start_epoch),history.history['val_reshape_2_loss'])
#        pylab.title('model loss (probability)')
#        pylab.ylabel('loss')
#        pylab.xlabel('epoch')
#        plt.grid(True)
#        pylab.legend(['train', 'test'], loc='upper right')
#        pdf_loss.savefig(1002)
        

    if EXTRA_VALIDATION :
        plt.figure(1003)
        pylab.plot(efficiency_4)
        pylab.plot(efficiency_8)
        pylab.title('Efficiency of track finding')
        pylab.ylabel('Efficiency')
        pylab.xlabel('epoch')
        plt.grid(True)
        pylab.legend(['thr=4', 'thr=8'], loc='upper left')
        pdf_loss.savefig(1003)
        
        plt.figure(1004)
        pylab.plot(fake_rate_4)
        pylab.plot(fake_rate_8)
        pylab.title('Fake Rate')
        pylab.ylabel('Fake Rate')
        pylab.xlabel('epoch')
        plt.grid(True)
        pylab.legend(['thr=4', 'thr=8'], loc='upper right')
        pdf_loss.savefig(1004)

    pdf_loss.close()


if PREDICT :

    print("prediction: start")

    if not TRAIN : #must be loaded previously produced weights, otherwise if you predict on the same sample of the training not needed
        #Barrel training (used in presentation, CMSSW PR...)
        ## model.load_weights('data/DeepCore_barrel_weights.246-0.87.hdf5')
        model.load_weights('Training_1019_9k/Deepcore_train_weights1019.h5')
        #EndCap training, last weights (not satisfactory, consider to restart)      
        # model.load_weights('DeepCore_ENDCAP_train_ep150.h5')
        #model.load_weights('DeepCore_train_ev{ev}_ep{ep}.h5'.format(ev=jetNum,ep=epochs+start_epoch)) 

    [validation_par,validation_prob] = model.predict([input_,input_jeta,input_jpt])
    validation_par = np.float64(validation_par)
    np.savez("DeepCore_prediction_ev{ev}".format(ev=jetNum), validation_par=validation_par, validation_prob=validation_prob)

    print("prediction: completed")



#------------------------------------------------------------------------------------------#
#------------------------------------- OUTPUT ROOT FILE -----------------------------------#
#------------------------------------------------------------------------------------------#


if OUTPUT :
     if PREDICT == False  and (not DRAW_ONLY):

        print("prediction loading: start")
        loadpred = np.load("DeepCore_prediction_ev{ev}.npz".format(ev=jetNum))#106.4

        validation_par = loadpred['validation_par']
        validation_prob = loadpred['validation_prob']

        print("prediction loading: completed")

     if(not ON_DATA) :
        target_prob = target_prob[:,:,:,:,:-1]
     if (not DRAW_ONLY):
        validation_prob = validation_prob[:,:,:,:,:-1]

     import ROOT
     from ROOT import gStyle
     from ROOT import gROOT
     gROOT.Reset()
     gROOT.SetBatch(True)
     gStyle.SetOptStat(0)
     validation_offset=int(len(input_)*(1-valSplit)+1)

     canvasTot = []
     canvasProb = []

     mapTot = []
     graphTargetTot = []
     mapProbPredTot = []
     graphPredTot = []


     for jet in range(numPrint) :

         canvasTot_jet = []
         mapTot_jet = []
         graphTargetTot_jet = []
         canvasProb_jet =[]
         mapProbPredTot_jet =[]
         graphPredTot_jet = []


         for trk in range(overlapNum) :
            canvasProb_jet.append(ROOT.TCanvas("canvasProb_%d_%d" % (jet,trk), "canvasProb_%d_%d" % (jet,trk),500,800))
            mapProbPredTot_jet.append(ROOT.TH2F("mapProbPredTot_%d_%d" % (jet,trk), "mapProbPredTot_%d_%d" % (jet,trk), jetDim,-jetDim/2,jetDim/2,jetDim,-jetDim/2,jetDim/2))

         for lay in range(layNum) :
             mapTot_jet.append(ROOT.TH2F("mapTot_%d_%d" % (jet, lay), "mapTot_%d_%d" % (jet, lay), jetDim,-jetDim/2,jetDim/2,jetDim,-jetDim/2,jetDim/2))
             canvasTot_jet.append(ROOT.TCanvas("canvasTot_%d_%d" % (jet, lay), "canvasTot_%d_%d" % (jet, lay),500,800))
             graphTargetTot_jet.append(ROOT.TGraph())
            #  graphPredTot_jet.append(ROOT.TGraph(overlapNum*3))
             graphPredTot_jet.append(ROOT.TGraph())

         mapTot.append(mapTot_jet)
         canvasTot.append(canvasTot_jet)
         graphTargetTot.append(graphTargetTot_jet)
         mapProbPredTot.append(mapProbPredTot_jet)
         canvasProb.append(canvasProb_jet)
         graphPredTot.append(graphPredTot_jet)





     for jet in range(numPrint) :
         print("=================================== New Event ======================================")

         j_eff = jet+validation_offset
        #  j_eff = jet #WARNING, is this intended? 

         #check if lay1 is broken
         brokenLay_flag = False
         brokenLay_cut = 0
         for x in range(jetDim) :
             for y in range(jetDim) :
                if(input_[j_eff][x][y][1] > 0.0001) :
                    brokenLay_flag = True
         if(not brokenLay_flag) :
            brokenLay_cut = 0.35

         # fill the histos   
         for lay in range(layNum) :
             tarPoint = 0
             predPoint = 0
             graphPredTot[jet][lay].SetMarkerColor(7)
             graphPredTot[jet][lay].SetMarkerStyle(28)
             graphPredTot[jet][lay].SetMarkerSize(3)
             graphTargetTot[jet][lay].SetMarkerColor(6)
             graphTargetTot[jet][lay].SetMarkerStyle(2)
             graphTargetTot[jet][lay].SetMarkerSize(3)
             for x in range(jetDim) :
                 for y in range(jetDim) :
                     mapTot[jet][lay].SetBinContent(x+1,y+1,input_[j_eff][x][y][lay])
                     if(input_[j_eff][x][y][lay]>0) : print("input pixel:", "(x,y)=",x,y, ", layer=",lay, ", value=", input_[j_eff][x][y][lay])
                     for trk in range(overlapNum) :
                        if not DRAW_ONLY : 
                            mapProbPredTot[jet][trk].SetBinContent(x+1,y+1,validation_prob[j_eff][x][y][trk])
                        if(not ON_DATA) :
                            if target_prob[j_eff][x][y][trk] == 1 and lay==1:
                                xx= float(target_[j_eff][x][y][trk][0])/float(0.01)*0.01#normaliz. factor
                                yy= float(target_[j_eff][x][y][trk][1])/float(0.015)*0.01
                                graphTargetTot[jet][lay].SetPoint(tarPoint,x+xx-jetDim/2,y+yy-jetDim/2)

                                x0,y0 = prop_on_layer(x+xx-jetDim/2, y+yy-jetDim/2,target_[j_eff][x][y][trk][2]*0.01,target_[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],0)
                                x2,y2 = prop_on_layer(x+xx-jetDim/2, y+yy-jetDim/2,target_[j_eff][x][y][trk][2]*0.01,target_[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],2)
                                x3,y3 = prop_on_layer(x+xx-jetDim/2, y+yy-jetDim/2,target_[j_eff][x][y][trk][2]*0.01,target_[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],3)
                                graphTargetTot[jet][0].SetPoint(tarPoint,x0,y0)
                                graphTargetTot[jet][2].SetPoint(tarPoint,x2,y2)
                                graphTargetTot[jet][3].SetPoint(tarPoint,x3,y3)
                                tarPoint = tarPoint+1
                        if not DRAW_ONLY :
                            if validation_prob[j_eff][x][y][trk] > (prob_thr-0.1*trk-brokenLay_cut) and lay==1 : #and   target_prob[j_eff][x][y][trk] == 1: #this is an useful option to debug
                                xx_pr= float(validation_par[j_eff][x][y][trk][0])/float(0.01)*0.01
                                yy_pr= float(validation_par[j_eff][x][y][trk][1])/float(0.015)*0.01
                                graphPredTot[jet][lay].SetPoint(predPoint,x+xx_pr-jetDim/2,y+yy_pr-jetDim/2)

                                x0,y0 = prop_on_layer(x+xx_pr-jetDim/2, y+yy_pr-jetDim/2,validation_par[j_eff][x][y][trk][2]*0.01,validation_par[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],0)
                                x2,y2 = prop_on_layer(x+xx_pr-jetDim/2, y+yy_pr-jetDim/2,validation_par[j_eff][x][y][trk][2]*0.01,validation_par[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],2)
                                x3,y3 = prop_on_layer(x+xx_pr-jetDim/2, y+yy_pr-jetDim/2,validation_par[j_eff][x][y][trk][2]*0.01,validation_par[j_eff][x][y][trk][3]*0.01,input_jeta[j_eff],3)
                                graphPredTot[jet][0].SetPoint(predPoint,x0,y0)
                                graphPredTot[jet][2].SetPoint(predPoint,x2,y2)
                                graphPredTot[jet][3].SetPoint(predPoint,x3,y3)
                                predPoint = predPoint+1

                                print("________________________________________")
                                print("New Pred, bin (x,y):",x-jetDim/2,y-jetDim/2)
                                if(not ON_DATA):
                                    print("target(x,y,eta,phi)=",target_[j_eff][x][y][trk][0]," ", target_[j_eff][x][y][trk][1]," ",target_[j_eff][x][y][trk][2]," ",target_[j_eff][x][y][trk][3]," ",target_[j_eff][x][y][trk][4],"Probabiity target=", target_prob[j_eff][x][y][trk])
                                    print("prediction(x,y,eta,phi)=",validation_par[j_eff][x][y][trk][0]," ", validation_par[j_eff][x][y][trk][1]," ",validation_par[j_eff][x][y][trk][2]," ",validation_par[j_eff][x][y][trk][3]," ",validation_par[j_eff][x][y][trk][4], "Probabiity pred=", validation_prob[j_eff][x][y][trk])
                                    print(" x0,y0=",x0,y0," x2,y2=",x2,y2," x3,y3=",x3,y3,)


     output_file = ROOT.TFile("DeepCore_mapValidation_ev{ev}.root".format(ev=jetNum),"recreate")
     from array import array as array2

     if(RGB) : #set the color scheme

         NCont=10

         array_of_palette = []
         palette = []

         Red =[1.,1.]
         Green =[1.,0.]
         Blue =[1.,0.]
         Stops =[0.,1.]
         StopsArray = array2('d', Stops)
         RedArray = array2('d', Red)
         GreenArray = array2('d', Green)
         BlueArray = array2('d', Blue)
         FI = TColor.CreateGradientColorTable(2, StopsArray, RedArray, GreenArray, BlueArray, NCont)
         for i in range(0,NCont) :
             palette.append(FI+i)
         paletteArray = array2('i',palette)
         palette[:]=[]
         array_of_palette.append(paletteArray)


         Red =[1.,0.]
         Green =[1.,0.]
         Blue =[1.,0.]
         Stops =[0.,1.]
         StopsArray = array2('d', Stops)
         RedArray = array2('d', Red)
         GreenArray = array2('d', Green)
         BlueArray = array2('d', Blue)
         FI = TColor.CreateGradientColorTable(2, StopsArray, RedArray, GreenArray, BlueArray, NCont)
         for i in range(0,NCont) :
             palette.append(FI+i)
         paletteArray = array2('i',palette)
         palette[:]=[]
         array_of_palette.append(paletteArray)

         Red =[1.,0]
         Green =[1.,1]
         Blue =[1.,0.]
         Stops =[0.,1.]
         StopsArray = array2('d', Stops)
         RedArray = array2('d', Red)
         GreenArray = array2('d', Green)
         BlueArray = array2('d', Blue)
         FI = TColor.CreateGradientColorTable(2, StopsArray, RedArray, GreenArray, BlueArray, NCont)
         for i in range(0,NCont) :
             palette.append(FI+i)
         paletteArray = array2('i',palette)
         palette[:]=[]
         array_of_palette.append(paletteArray)

         Red =[1.,0.]
         Green =[1.,0.]
         Blue =[1.,1.]
         Stops =[0.,1.]
         StopsArray = array2('d', Stops)
         RedArray = array2('d', Red)
         GreenArray = array2('d', Green)
         BlueArray = array2('d', Blue)
         FI = TColor.CreateGradientColorTable(2, StopsArray, RedArray, GreenArray, BlueArray, NCont)
         for i in range(0,NCont) :
             palette.append(FI+i)
         paletteArray = array2('i',palette)
         palette[:]=[]
         array_of_palette.append(paletteArray)

     # build the cavases
     for jet in range(numPrint) :

         #check if lay1 is broken!
         brokenLay_flag = False
         brokenLay_cut = 0
         for x in range(jetDim) :
             for y in range(jetDim) :
                if(input_[jet][x][y][1] > 0.0001) :
                    brokenLay_flag = True
         if(not brokenLay_flag) :
            brokenLay_cut = 0.35

         for lay in range(layNum) :
             canvasTot[jet][lay].cd()
             mapTot[jet][lay].GetXaxis().SetRangeUser(-jetDim,jetDim)
             mapTot[jet][lay].GetYaxis().SetRangeUser(-jetDim,jetDim)
            #  mapTot[jet][lay].SetTitle("Pixel Map, cluster %d, layer %d, pt=%f, eta=%f" % (jet, lay+1, input_jpt[jet],input_jeta[jet]))
             mapTot[jet][lay].SetTitle("Pixel Window, layer %d" % (lay+1))
             mapTot[jet][lay].GetXaxis().SetTitle("x [pixel]")
             mapTot[jet][lay].GetYaxis().SetTitle("y [pixel]")
             mapTot[jet][lay].GetYaxis().SetTitleOffset(1)
             mapTot[jet][lay].GetZaxis().SetTitle("ADC count [/14k]")
             mapTot[jet][lay].GetZaxis().SetTitleOffset(-1.05)
             mapTot[jet][lay].GetXaxis().SetTitleSize(0.06)
             mapTot[jet][lay].GetYaxis().SetTitleSize(0.06)
             mapTot[jet][lay].GetZaxis().SetTitleSize(0.04)
             mapTot[jet][lay].GetXaxis().SetTitleOffset(0.7)
             mapTot[jet][lay].GetYaxis().SetTitleOffset(0.6)

             latexCMS = ROOT.TLatex()


             if(not RGB) :
                 mapTot[jet][lay].Draw("colz")

                 latexCMS.SetTextSize(0.05)
                 latexCMS.DrawLatex(-16.2,16.2,"#bf{#bf{CMS}} #scale[0.7]{#bf{#it{Simulation Preliminary}}}")
                 latexCMS.DrawLatex(12,16.2,"#bf{13 TeV}")

             else :
                 gStyle.SetPalette(NCont,array_of_palette[lay])
                 mapTot[jet][lay].Draw("colz")

                 latexCMS.SetTextSize(0.05)
                 latexCMS.DrawLatex(-16.2,16.2,"#bf{#bf{CMS}} #scale[0.7]{#bf{#it{Simulation Preliminary}}}")
                 latexCMS.DrawLatex(12,16.2,"#bf{13 TeV}")

             if(jet==outEvent and RGB):


                 mapTot[jet][lay].GetZaxis().SetRangeUser(0,2.7)
                 canvasTot[jet][lay].SaveAs("RGB_PixelMap_input_layer%d_event%d.pdf" % (lay,jet))
                 canvasTot[jet][lay].SaveAs("RGB_PixelMap_input_layer%d_event%d.png" % (lay,jet))

             if (not ON_DATA) :
                 graphTargetTot[jet][lay].Draw("SAME P")
             graphPredTot[jet][lay].Draw("SAME P")

             graphTargetTot[jet][lay].SetLineColor(0)
             graphPredTot[jet][lay].SetLineColor(0)
             graphTargetTot[jet][lay].SetFillColor(0)
             graphPredTot[jet][lay].SetFillColor(0)

             latexCMS.SetTextSize(0.05)
             latexCMS.DrawLatex(-16.2,16.2,"#bf{#bf{CMS}} #scale[0.7]{#bf{#it{Simulation Preliminary}}}")
             latexCMS.DrawLatex(12,16.2,"#bf{13 TeV}")



             legTot = ROOT.TLegend(0.1,0.9,0.3,0.8);
             if (not ON_DATA) :
                 legTot.AddEntry(graphTargetTot[jet][lay], "Target")
             legTot.AddEntry(graphPredTot[jet][lay], "Prediction")
             legTot.SetTextSize(0.03);
             legTot.Draw("SAME")

             canvasTot[jet][lay].Write()

             if(jet==outEvent and RGB):
                 canvasTot[jet][lay].SaveAs("RGB_PixelMap_crosses_layer%d_event%d.pdf" % (lay,jet))
                 canvasTot[jet][lay].SaveAs("RGB_PixelMap_crosses_layer%d_event%d.png" % (lay,jet))

         for trk in range(overlapNum) :
             canvasProb[jet][trk].cd()
             mapProbPredTot[jet][trk].GetXaxis().SetRangeUser(-jetDim,jetDim)
             mapProbPredTot[jet][trk].GetYaxis().SetRangeUser(-jetDim,jetDim)
             gStyle.SetPalette(57)
             mapProbPredTot[jet][trk].Draw("colz")
             mapProbPredTot[jet][trk].GetXaxis().SetTitle("x [pixel]")
             mapProbPredTot[jet][trk].GetYaxis().SetTitle("y [pixel]")
             mapProbPredTot[jet][trk].GetYaxis().SetTitleOffset(1.2)
            #  mapProbPredTot[jet][trk].SetTitle("TCP Prediction Map, cluster %d, overlap %d" % (jet, trk))
             mapProbPredTot[jet][trk].SetTitle("TCP Prediction Map, overlap %d" % (trk))
             mapProbPredTot[jet][trk].GetZaxis().SetTitle("Probability")
             mapProbPredTot[jet][trk].GetZaxis().SetTitleOffset(-1.05)
             mapProbPredTot[jet][trk].GetXaxis().SetTitleSize(0.06)
             mapProbPredTot[jet][trk].GetYaxis().SetTitleSize(0.06)
             mapProbPredTot[jet][trk].GetXaxis().SetTitleOffset(0.7)
             mapProbPredTot[jet][trk].GetYaxis().SetTitleOffset(0.6)
             if (not ON_DATA) :
                 graphTargetTot[jet][1].Draw("SAME P")
             graphPredTot[jet][1].Draw("SAME P")

             latexCMS.SetTextSize(0.05)
             latexCMS.DrawLatex(-16.2,16.2,"#bf{#bf{CMS}} #scale[0.7]{#bf{#it{Simulation Preliminary}}}")
             latexCMS.DrawLatex(12,16.2,"#bf{13 TeV}")


             legProb = ROOT.TLegend(0.1,0.9,0.3,0.8);
             if (not ON_DATA) :
                legProb.AddEntry(graphTargetTot[jet][1], "Target")
             legProb.AddEntry(graphPredTot[jet][1], "Prediction")
             legProb.SetTextSize(0.03);
             legProb.Draw("SAME")

             mapProbPredTot[jet][0].GetZaxis().SetRangeUser(0,1)
             canvasProb[jet][trk].Write()

         if(jet==outEvent and RGB):
             canvasProb[jet][0].SaveAs("Probabiltiy_crosses_event%d.pdf" % (jet))#.png
             canvasProb[jet][0].SaveAs("Probabiltiy_crosses_event%d.png" % (jet))#.png

     output_file.Close()

     #plot of parameters distributions and residuals
     if(not ON_DATA) : 
         print("parameter file: start looping")
         pdf_par = mpl.backends.backend_pdf.PdfPages("parameter_file_ev{ev}.pdf".format(ev=jetNum))

         for par in range(parNum) :
             bins = []# np.zeros(shape=(int(jetNum*valSplit)))
             bins_pred = []
             bins_target = []
             nbin =0
             n_sig_ok = 0
             for j in range (int(len(input_))) :
                 j_eff = j
                #  j_eff=j+validation_offset use this if you want to avoid to fill the histos with the event used in the training, but you have also to change the j range()
                 for x in range(jetDim) :
                     for y in range(jetDim) :
                         for trk in range(overlapNum) :
                             if target_prob[j_eff][x][y][trk] == 1 :
                            #  if validation_prob[j_eff][x][y][trk] > prob_thr-0.1*trk-brokenLay_cut  and target_prob[j_eff][x][y][trk] == 1:# only "associated" 
                                     if(par!=4) :
                                         if not DRAW_ONLY : bins.append((validation_par[j_eff][x][y][trk][par] - target_[j_eff][x][y][trk][par])*0.01)
                                         if not DRAW_ONLY : bins_pred.append(validation_par[j_eff][x][y][trk][par]*0.01)
                                         bins_target.append(target_[j_eff][x][y][trk][par]*0.01)
                                     else :
                                         if not DRAW_ONLY : bins.append((validation_par[j_eff][x][y][trk][par] - target_[j_eff][x][y][trk][par])/target_[j_eff][x][y][trk][par])  #relative
                                         if not DRAW_ONLY :  bins_pred.append(validation_par[j_eff][x][y][trk][par])
                                         bins_target.append(target_[j_eff][x][y][trk][par])
                                     nbin = nbin+1
                                     if not DRAW_ONLY :
                                          if(validation_par[j_eff][x][y][trk][par]*target_[j_eff][x][y][trk][par]>0) : #same Sign
                                            n_sig_ok = n_sig_ok+1
             if nbin>0 :
                 fracsig=n_sig_ok/float(nbin)
             else :
                 fracsig = 0
             print("Parameter {PAR}, number of correct sign={n}, fraction={f}".format(PAR=par, n=n_sig_ok, f=fracsig))
             plt.figure()
             if(par!=4) :
                 pylab.hist(bins,70, facecolor='darkorange', alpha=0.75, range=(-0.03,0.03))
             else :
                 pylab.hist(bins,200, facecolor='darkorange', alpha=0.75, range=(-2,5))#range=(-0.2,0.2))#range=(-2,5)) #relative
             if(par == 0) :
                 pylab.title('Residual distribution - x',fontsize=22)
             if(par == 1) :
                 pylab.title('Residual distribution - y',fontsize=22)
             if(par == 2) :
                 pylab.title('Residual distribution - $\eta$',fontsize=22)
                 plt.text(-0.032,1030, "CMS ", weight='bold', size=17)
                 plt.text(-0.032,950, "Simulation Preliminary", style='italic', size=14)
                 plt.text(0.0215,1030, "13 TeV", size = 17)
                 plt.text(0.0025,915, r'QCD events ($\langle PU \rangle=30$)',size=14)
                 plt.text(0.0025,830,r'1.8 TeV $<\hat p_T<$2.4 TeV',size=14)
                 plt.text(0.0025,745,r'$p_T^{jet}>1$ TeV, $|\eta^{jet}|<1.4$',size=14)
                 if not DRAW_ONLY : mean = np.array(bins).mean()
                 if not DRAW_ONLY : sigma = np.array(bins).std()
                #if not DRAW_ONLY :  plt.text(0.009, 550, "Mean =%f"%(mean), size=14)
                 if not DRAW_ONLY : plt.text(0.0145, 465, "$\sigma_{res}$ = %.3f"%(sigma), size=14)

             if(par == 3) :
                 pylab.title('Residual distribution - $\phi$',fontsize=22)
             if(par == 4) :
                 pylab.title('Residual distribution - $p_T$',fontsize=22)
             pylab.ylabel('Events/0.0008',fontsize=18)
             pylab.xlabel('(prediction-target)/target',fontsize=18) #only 1/pt
             if(par==0 or par==1) : #relative
                 pylab.xlabel('prediction-target [cm]',fontsize=22)
             elif(par==2 or par==3) : #relative
                 pylab.xlabel('prediction-target',fontsize=22)
            #  else : #relative
            #      pylab.xlabel('prediction-target [1/GeV]',fontsize=22)

             plt.grid(True)
             if(RGB) :
                 pylab.savefig("residual_{jj}_{PAR}.pdf".format(PAR=par,jj=jetNum))#.png
                 pylab.savefig("residual_{jj}_{PAR}.png".format(PAR=par,jj=jetNum))#.png

             pdf_par.savefig()

             plt.figure()
             if(par!=4) :
                 pylab.hist(bins_target,70, facecolor='royalblue', alpha=0.75, range=(-0.03,0.03))
             else :
                 pylab.hist(bins_target,100, facecolor='royalblue', alpha=0.75, range=(-0,0.2))

             if(par == 0) :
                 pylab.title('Target distribution - x',fontsize=22)
             if(par == 1) :
                 pylab.title('Target distribution - y',fontsize=22)
             if(par == 2) :
                 pylab.title('Target distribution - $\eta$',fontsize=22)
             if(par == 3) :
                 pylab.title('Target distribution - $\phi$',fontsize=22)
             if(par == 4) :
                 pylab.title('Target distribution - $p_T$',fontsize=22)
             if(par==0 or par==1) :
                 pylab.xlabel('target [cm]',fontsize=18)
             elif(par==2 or par==3) :
                 pylab.xlabel('target',fontsize=18)
             else :
                 pylab.xlabel('prediction-target [1/GeV]',fontsize=18)
             pylab.ylabel('entries',fontsize=18)
             plt.grid(True)
             if(RGB) :
                 pylab.savefig("target_{jj}_{PAR}.pdf".format(PAR=par,jj=jetNum))#.png
                 pylab.savefig("target_{jj}_{PAR}.png".format(PAR=par,jj=jetNum))#.png

             pdf_par.savefig()

             plt.figure()
             if(par!=4) :
                 pylab.hist(bins_pred,70, facecolor='red', alpha=0.75, range=(-0.03,0.03))
             else :
                 pylab.hist(bins_pred,200, facecolor='red', alpha=0.75, range=(-0.2,0.2))

             if(par == 0) :
                 pylab.title('Prediction distribution - x',fontsize=22)
             if(par == 1) :
                 pylab.title('Prediction distribution - y',fontsize=22)
             if(par == 2) :
                 pylab.title('Prediction distribution - $\eta$',fontsize=22)
             if(par == 3) :
                 pylab.title('Prediction distribution - $\phi$',fontsize=22)
             if(par == 4) :
                 pylab.title('Prediction distribution - $p_T$',fontsize=22)
             if(par==0 or par==1) :
                 pylab.xlabel('prediction [cm]',fontsize=18)
             elif(par==2 or par==3) :
                 pylab.xlabel('prediction',fontsize=18)
             else :
                 pylab.xlabel('prediction-target [1/GeV]',fontsize=18)
             pylab.ylabel('entries',fontsize=18)
             plt.grid(True)
             if(RGB) :
                 pylab.savefig("prediction_{jj}_{PAR}.pdf".format(PAR=par,jj=jetNum))#.png
                 pylab.savefig("prediction_{jj}_{PAR}.png".format(PAR=par,jj=jetNum))#.png

             pdf_par.savefig()

             #scatter plot
             if(not DRAW_ONLY) :
                 plt.figure()
                 if(par == 0) :
                     plt.hist2d(bins_pred,bins_target,bins=50,range = [[-0.015, 0.015], [-0.015, 0.015]], cmap=plt.cm.viridis)#, marker='+')
                     plt.xlabel('x prediction [cm]')
                     plt.ylabel('x target [cm]')
                     plt.colorbar()
                 if(par == 1) :
                     plt.hist2d(bins_pred,bins_target,bins=50,range = [[-0.02, 0.02], [-0.02, 0.02]], cmap=plt.cm.viridis)
                     plt.xlabel('y prediction [cm]')
                     plt.ylabel('y target [cm]')
                     plt.colorbar()
                 if(par == 2) :
                     plt.hist2d(bins_pred,bins_target,bins=50,range = [[-0.03, 0.03], [-0.03, 0.03]], cmap=plt.cm.viridis)
                     plt.xlabel('$\eta$ prediction', fontsize=18, labelpad=-5)
                     plt.ylabel('$\eta$ target', fontsize=18, labelpad=-5)
                     plt.colorbar()
                     plt.text(-0.029,0.026, "CMS ", weight='bold', size=17, color="white")
                     plt.text(-0.029,0.023, "Simulation Preliminary", style='italic', size=14, color="white")
                     plt.text(0.017,0.026, "13 TeV", size = 17,color="white")
                     plt.text(-0.005,-0.015, r'QCD events ($\langle PU \rangle=30$)',size=14,color="white")
                     plt.text(-0.005,-0.02,r'1.8 TeV $<\hat p_T<$2.4 TeV',size=14,color="white")
                     plt.text(-0.005,-0.025,r'$p_T^{jet}>1$ TeV, $|\eta^{jet}|<1.4$',size=14,color="white")


                 if(par == 3) :
                     plt.hist2d(bins_pred,bins_target,bins=50,range = [[-0.03, 0.03], [-0.03, 0.03]], cmap=plt.cm.viridis)
                     plt.xlabel('$\phi$ prediction')
                     plt.ylabel('$\phi$ target')
                     plt.colorbar()
                 if(par == 4) :
                     plt.hist2d(bins_pred,bins_target,bins=30,range = [[0, 0.15], [0, 0.15]])
                     plt.xlabel('$p_T$ prediction [1/GeV]')
                     plt.ylabel('$p_T$ target [1/GeV]')
                     plt.colorbar()
                 if(RGB) :
                     pylab.savefig("predVStarget_{jj}_{PAR}.pdf".format(PAR=par,jj=jetNum))#.png
                     pylab.savefig("predVStarget_{jj}_{PAR}.png".format(PAR=par,jj=jetNum))#.png

                 pdf_par.savefig()
         pdf_par.close()
