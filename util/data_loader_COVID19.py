'''
data_loader
'''
from glob import glob
import torch
# from random import random, shuffle
from torchvision import transforms
import torchvision.transforms.functional as F
from timm.data import create_transform
from torchvision.transforms import InterpolationMode
import numpy as np
from main_finetune_txt_ddp import set_seed
from torch.utils.data import Dataset
from PIL import Image
from util.crop import RandomResizedCrop
from timm.data.constants import IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD

def read_txt(txt_path):
    with open(txt_path) as f:
        lines = f.readlines()
    txt_data = [line.strip() for line in lines]
    return txt_data

class CovidCTDataset(Dataset):
    def __init__(self, data_list, transform=None):
        """
        Args:
            txt_path (string): Path to the txt file with annotations.
            root_dir (string): Directory with all the images.
            transform (callable, optional): Optional transform to be applied
                on a sample.
        File structure:
        - root_dir
            - COVID
                - img1.png
                - img2.png
                - ......
            - non-COVID
                - img1.png
                - img2.png
                - ......
        """
        self.transform = transform
        self.img_list = [item.split('\t') for item in data_list]

    def __len__(self):
        return len(self.img_list)
    
    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        img_path = self.img_list[idx][0]
        while True:
            try:
                image = Image.open(img_path).convert('RGB')
            except OSError as e:
                print('Transport endpoint is not connected...')
                import time
                time.sleep(1)
            else:
                break
        if self.transform:
            image = self.transform(image)
        label = int(self.img_list[idx][1])
        label = torch.tensor(int(label))
        return image, label

def split_list(COVID_pth,NonCOVID_pth,args):
    f1 = open(COVID_pth,'r')
    COVID = f1.readlines()
    f2 = open(NonCOVID_pth,'r')
    NonCOVID = f2.readlines()

    set_seed(args.seed)
    np.random.shuffle(COVID)
    np.random.shuffle(NonCOVID)

    split_ratio=list(map(float,args.split_ratio.split(':')))
    # train_COVID = COVID[:int(split_ratio[0]/10*len(COVID))]
    # val_COVID = COVID[int(split_ratio[0]/10*len(COVID)):int((split_ratio[0]+split_ratio[1])/10*len(COVID))]
    # test_COVID = COVID[int((split_ratio[0]+split_ratio[1])/10*len(COVID)):]

    # train_NonCOVID = NonCOVID[:int(split_ratio[0]/10*len(NonCOVID))]
    # val_NonCOVID = NonCOVID[int(split_ratio[0]/10*len(NonCOVID)):int((split_ratio[0]+split_ratio[1])/10*len(NonCOVID))]
    # test_NonCOVID = NonCOVID[int((split_ratio[0]+split_ratio[1])/10*len(NonCOVID)):]

    print('$$$$$$$$',int((split_ratio[0]+split_ratio[1])))
    test_COVID = COVID[int((split_ratio[0]+split_ratio[1])/10*len(COVID)):]
    test_NonCOVID = NonCOVID[int((split_ratio[0]+split_ratio[1])/10*len(NonCOVID)):]
    test_list = test_COVID + test_NonCOVID
    np.random.shuffle(test_list)

    set_seed(args.seed)
    non_test_COVID = COVID[:int((split_ratio[0]+split_ratio[1])/10*len(COVID))]
    non_test_NonCOVID = NonCOVID[:int((split_ratio[0]+split_ratio[1])/10*len(NonCOVID))]
    np.random.shuffle(non_test_COVID)
    np.random.shuffle(non_test_NonCOVID)
    train_COVID = non_test_COVID[:int(split_ratio[0]/(split_ratio[0]+split_ratio[1])*len(non_test_COVID))]
    val_COVID = non_test_COVID[int(split_ratio[0]/(split_ratio[0]+split_ratio[1])*len(non_test_COVID)):]
    train_NonCOVID = non_test_NonCOVID[:int(split_ratio[0]/(split_ratio[0]+split_ratio[1])*len(non_test_NonCOVID))]
    val_NonCOVID = non_test_NonCOVID[int(split_ratio[0]/(split_ratio[0]+split_ratio[1])*len(non_test_NonCOVID)):]

    train_list = train_COVID + train_NonCOVID
    val_list = val_COVID + val_NonCOVID

    np.random.shuffle(train_list)
    np.random.shuffle(val_list)
    # with open('./test_list/train_list%20_seed{}.txt'.format(args.seed),'a') as f:
        # f.writelines(train_list)
    # with open('./test_list/val_list%30_seed{}.txt'.format(args.seed),'w') as f:
        # f.writelines(val_list)
    # with open('./test_list/test_list%50_seed{}_fixed.txt'.format(args.seed),'a') as f:
        # f.writelines(test_list)

    return train_list,val_list,test_list

def build_transform(is_train, args):
    mean = IMAGENET_DEFAULT_MEAN
    std = IMAGENET_DEFAULT_STD
    # train transform
    if is_train:
        # this should always dispatch to transforms_imagenet_train
        transform = create_transform(
            input_size=args.input_size,
            is_training=True,
            color_jitter=args.color_jitter,
            auto_augment=args.aa,
            interpolation='bicubic',
            re_prob=args.reprob,
            re_mode=args.remode,
            re_count=args.recount,
            mean=mean,
            std=std,
        )
        return transform

    # eval transform
    t = []
    if args.input_size <= 224:
        crop_pct = 224 / 256
    else:
        crop_pct = 1.0
    size = int(args.input_size / crop_pct)
    t.append(
        transforms.Resize(size, interpolation = InterpolationMode.BICUBIC),  # to maintain same ratio w.r.t. 224 images
    )
    t.append(transforms.CenterCrop(args.input_size))
    t.append(transforms.ToTensor())
    t.append(transforms.Normalize(mean, std))
    return transforms.Compose(t)

#linear probe: weak augmentation
def load_linprobe(args):
    dataset_name = {                    
            'U_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_orig',
            'U_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_sani',
            'U_sani2':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_sani2',
            'C_SI_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/C_SI_orig',
            'SI_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/siim_covid19_detection_xray/SI_orig',
            'SI_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/siim_covid19_detection_xray/SI_sani'
        }
    transform_dict = {
        'train': transforms.Compose([
            RandomResizedCrop(224, interpolation=3),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])]),
        'val': transforms.Compose([
            transforms.Resize(256, interpolation=3),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
        }

    COVID_pth='{}/COVID.txt'.format(dataset_name[args.tar])
    NonCOVID_pth='{}/non-COVID.txt'.format(dataset_name[args.tar])
    train_list,val_list,test_list = split_list(COVID_pth, NonCOVID_pth,args)
    
    trainset = CovidCTDataset(train_list,transform=transform_dict['train'])
    valset = CovidCTDataset(val_list,transform=transform_dict['val'])
    testset = CovidCTDataset(test_list,transform=transform_dict['val'])

    return trainset, valset, testset


def load_finetune(args):
    dataset_name = {
                    'U_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_orig',
                    'U_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_sani',
                    'U_sani2':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/UCSD_AI4H_COVID_CT_data/Images-processed/U_sani2',
                    'C_SI_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/C_SI_orig',
                    'SI_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/siim_covid19_detection_xray/SI_orig',
                    'SI_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4finetune/siim_covid19_detection_xray/SI_sani'
               }

    transform_dict = {
        'train': build_transform(True, args),
        'val': build_transform(False, args),
        'test': build_transform(False, args)
        }
        
    COVID_pth='{}/COVID.txt'.format(dataset_name[args.tar])
    NonCOVID_pth='{}/non-COVID.txt'.format(dataset_name[args.tar])
    train_list,val_list,test_list = split_list(COVID_pth, NonCOVID_pth,args)
    
    trainset = CovidCTDataset(train_list,transform=transform_dict['train'])
    valset = CovidCTDataset(val_list,transform=transform_dict['val'])
    testset = CovidCTDataset(test_list,transform=transform_dict['test'])

    return trainset, valset, testset

def load_pretrain(args, transform):
    dataset_name = {
                    'CHE':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/chest-ct-scans-with-COVID-19/nii2png',
                    'CCT':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID-19_ct_scans1/ct_scans',
                    'C1920':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID-19-20_v2/data',
                    'CAR':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID-19-AR',
                    'CCS':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID-19-CT-segmentation-dataset',
                    'C1000':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID19-CT-Dataset1000+/data',
                    'CIC':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/CT_Images_in_COVID-19/nii2png',
                    'MRA':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/MIDRC-RICORD-1A',
                    'MRB':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/MIDRC-RICORD-1B',
                    'S_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/sarscov2_ctscan_dataset',
                    'SIRM':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/SIRM-COVID-19',
                    'CXC':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVIDX_CT_2A/CXC/backup4ft',
                        'C_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVIDX_CT_2A/C_sani',
                        'C_sani2':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVIDX_CT_2A/C_sani2',
                    'L_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/large_COVID_19_ct_slice_dataset/curated_data/L_orig',
                        'L_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/large_COVID_19_ct_slice_dataset/curated_data/L_sani',
                        'L_sani2':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/large_COVID_19_ct_slice_dataset/curated_data/L_sani2',
                    'CC_orig':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID_19_and_common_pneumonia_chest_CT_dataset/CC_orig',
                        'CC_sani':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID_19_and_common_pneumonia_chest_CT_dataset/CC_sani',
                        'CC_sani2':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-CT/COVID_19_and_common_pneumonia_chest_CT_dataset/CC_sani2',
                    'CXSD':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/COVID-19-chest-xray-segmentations-dataset',
                    'CRDX':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/COVID-19-radiography-database',
                    'CDX':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/COVID_DA_Xray',
                    'QUEX':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/COVID_QU_Ex_Dataset_Xray',
                    'CCXD':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/Coronahack-Chest-XRay-Dataset',
                    'MRC':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/MIDRC-RICORD-1C',
                    'CHEXD':'/sharefs/baaihealth/public_datasets/public_medical_images/datasets/selected4pretrain/COVID-nonCT/covid-chestxray-dataset'
                }
    transform_dict = {
        'train': transform,
        }
    # args.dataset_path = {'data_path': dataset_name[args.dataset]}
    train_list = []
    for dataset in args.dataset:
        txt_path = glob('{}/*.txt'.format(dataset_name[dataset]))
        for txt in txt_path:
            with open(txt) as f:
                lines = f.readlines()
                for line in lines:
                    train_list.append(line)
    np.random.shuffle(train_list)
    trainset = CovidCTDataset(train_list,transform=transform_dict['train'])
    return trainset

