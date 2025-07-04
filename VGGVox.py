#! /usr/bin/python
# -*- encoding: utf-8 -*-

import torch
import torchaudio
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import Parameter

class MainModel(nn.Module):
    def __init__(self, nout=100, encoder_type='SAP', log_input=True, **kwargs):
        super(MainModel, self).__init__()

        print('Embedding size is %d, encoder %s.'%(nout, encoder_type))
        
        self.encoder_type = encoder_type
        self.log_input = log_input

        self.netcnn = nn.Sequential(
            nn.Conv2d(1, 96, kernel_size=(5, 7), stride=(1, 2), padding=(2, 2)),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(1, 3), stride=(1, 2)),

            nn.Conv2d(96, 256, kernel_size=(5, 5), stride=(2, 2), padding=(1, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(3, 3), stride=(2, 2)),

            nn.Conv2d(256, 384, kernel_size=(3, 3), padding=(1, 1)),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),

            nn.Conv2d(384, 256, kernel_size=(3, 3), padding=(1, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),

            nn.Conv2d(256, 256, kernel_size=(3,3), padding=(1,1)),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(3, 3), stride=(2, 2)),

            nn.Conv2d(256, 512, kernel_size=(4, 1), padding=(0, 0)),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            
        )

        if self.encoder_type == "MAX":
            self.encoder = nn.AdaptiveMaxPool2d((1, 1))
            out_dim = 512
        elif self.encoder_type == "TAP":
            self.encoder = nn.AdaptiveAvgPool2d((1, 1))
            out_dim = 512
        elif self.encoder_type == "SAP":
            self.sap_linear = nn.Linear(512, 512)
            self.attention = self.new_parameter(512, 1)
            out_dim = 512
        else:
            raise ValueError('Undefined encoder')

        self.fc = nn.Linear(out_dim, nout)

        #self.instancenorm = nn.InstanceNorm1d(40)
        #self.torchfb = torchaudio.transforms.MelSpectrogram(sample_rate=16000, n_fft=512, win_length=400, hop_length=160, f_min=0.0, f_max=8000, pad=0, n_mels=40)

    def new_parameter(self, *size):
        out = nn.Parameter(torch.FloatTensor(*size))
        nn.init.xavier_normal_(out)
        return out
        
    def forward(self, x):

        # with torch.no_grad():
        #    with torch.cuda.amp.autocast(enabled=False):
        #        x = self.torchfb(x)+1e-6
        #        if self.log_input: x = x.log()
        #        x = self.instancenorm(x).unsqueeze(1)

        x = self.netcnn(x)

        if self.encoder_type == "MAX" or self.encoder_type == "TAP":
            x = self.encoder(x)
            x = x.view((x.size()[0], -1))

        elif self.encoder_type == "SAP":
            x = x.permute(0, 2, 1, 3)
            x = x.squeeze(dim=1).permute(0, 2, 1)  # batch * L * D
            h = torch.tanh(self.sap_linear(x))
            w = torch.matmul(h, self.attention).squeeze(dim=2)
            w = F.softmax(w, dim=1).view(x.size(0), x.size(1), 1)
            x = torch.sum(x * w, dim=1)

        x = self.fc(x)

        return x

