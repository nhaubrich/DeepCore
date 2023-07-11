import CRABClient
from WMCore.Configuration import Configuration
config = Configuration()

config.section_("General")
### Request Name
#config.General.requestName = 'DeepCore_12034_step3_JC'
#config.General.requestName = 'DeepCore_12034_step3_DC10'
config.General.requestName = 'DeepCore_12034_step3_DC213'

config.General.workArea = 'workflow_crab_12034'
config.General.transferOutputs = True
config.General.transferLogs = True

config.section_("JobType")
#config.JobType.pluginName = 'PrivateMC'
config.JobType.pluginName = 'Analysis'

### Config files
config.JobType.psetName = 'cmsDriver_step3.py'

#config.JobType.allowUndistributedCMSSW = True
config.JobType.numCores=8
config.JobType.maxMemoryMB=20000

config.section_("Data")
config.Data.inputDataset = '/DeepCore_12034_step12/hboucham-DeepCore_12034_step12-852344e9c9eb7309f0f090f422b57b9c/USER'
config.Data.splitting = 'FileBased'
config.Data.inputDBS = 'phys03'
config.Data.unitsPerJob = 1
config.Data.publication = False

### output tag
#config.Data.outputDatasetTag = 'DeepCore_12034_step3_JC'
#config.Data.outputDatasetTag = 'DeepCore_12034_step3_DC10'
config.Data.outputDatasetTag = 'DeepCore_12034_step3_DC213'

config.section_("Site")
#config.Site.storageSite = 'T3_CH_CERNBOX'
config.Site.storageSite = 'T3_US_FNALLPC'

config.section_("Debug")
config.Debug.extraJDL = ['+CMS_ALLOW_OVERFLOW=False']

