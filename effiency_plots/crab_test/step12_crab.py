import CRABClient
from WMCore.Configuration import Configuration
config = Configuration()

config.section_("General")
config.General.requestName = 'DeepCore_12034_step12'
config.General.workArea = 'workflows_crab_12034'
config.General.transferOutputs = True
config.General.transferLogs = True

config.section_("JobType")
config.JobType.pluginName = 'PrivateMC'
config.JobType.psetName = 'cmsDriver_step12.py'
config.JobType.allowUndistributedCMSSW = True
config.JobType.numCores=8
config.JobType.maxMemoryMB=20000

config.section_("Data")
config.Data.outputPrimaryDataset = 'DeepCore_12034_step12'
config.Data.splitting = 'EventBased'
config.Data.unitsPerJob = 100 #QCD
#config.Data.unitsPerJob = 200 #TTbar
NJOBS = 10 #QCD
#NJOBS = 50 #TTbar
config.Data.totalUnits = config.Data.unitsPerJob * NJOBS
config.Data.publication = True
config.Data.outputDatasetTag = 'DeepCore_12034_step12'

config.section_("Site")

#config.Site.storageSite = 'T3_CH_CERNBOX'
config.Site.storageSite = 'T3_US_FNALLPC'
