# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import sys
import time
import numpy as np
import os
import struct
from keras.engine.topology import Layer
from keras.callbacks import Callback
from keras.models import Model
from keras import backend as K
from keras.layers import Input
import keras.activations as activations
from keras.layers.merge import Multiply
from keras import optimizers
import tensorflow as tf
from keras.datasets import mnist


train_end_epochs = []

class MyEarlyStopping(Callback):
    def __init__(self, monitor='val_loss',
                 min_delta=0, patience=0, verbose=0, mode='auto'):
        super(MyEarlyStopping, self).__init__()

        self.monitor = monitor
        self.patience = patience
        self.verbose = verbose
        self.min_delta = min_delta
        self.wait = 0
        self.stopped_epoch = 0

        if mode not in ['auto', 'min', 'max']:
            warnings.warn('EarlyStopping mode %s is unknown, '
                          'fallback to auto mode.' % mode,
                          RuntimeWarning)
            mode = 'auto'

        if mode == 'min':
            self.monitor_op = np.less
        elif mode == 'max':
            self.monitor_op = np.greater
        else:
            if 'acc' in self.monitor:
                self.monitor_op = np.greater
            else:
                self.monitor_op = np.less

        if self.monitor_op == np.greater:
            self.min_delta *= 1
        else:
            self.min_delta *= -1

    def on_train_begin(self, logs=None):
        # Allow instances to be re-used
        self.wait = 0
        self.stopped_epoch = 0
        self.best = np.Inf if self.monitor_op == np.less else -np.Inf

    def on_epoch_end(self, epoch, logs=None):
        current = logs.get(self.monitor)
        if current is None:
            warnings.warn(
                'Early stopping conditioned on metric `%s` '
                'which is not available. Available metrics are: %s' %
                (self.monitor, ','.join(list(logs.keys()))), RuntimeWarning
            )
            return
        if self.monitor_op(current - self.min_delta, self.best):
            self.best = current
            self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.stopped_epoch = epoch
                self.model.stop_training = True

    def on_train_end(self, logs=None):
        global train_end_epochs
        train_end_epochs.append(self.stopped_epoch)
        if self.stopped_epoch > 0 and self.verbose > 0:
            print('Epoch %05d: early stopping' % (self.stopped_epoch + 1))
            
class MaskedDenseLayer(Layer):
    def __init__(self, output_dim, masks ,activation, **kwargs):
        self.output_dim = output_dim
        super(MaskedDenseLayer, self).__init__(**kwargs)
        self._mask = masks
        self._activation = activations.get(activation)
    def build(self, input_shape):
        # Create a trainable weight variable for this layer.
        self.kernel = self.add_weight(name='kernel', 
                                      shape=(input_shape[0][1], self.output_dim),
                                      initializer='glorot_uniform',
                                      trainable=True,
                                      dtype='float32')
        super(MaskedDenseLayer, self).build(input_shape)  # Be sure to call this somewhere!

    
    def call(self, l):
        self.x = l[0]
        self._state = l[1]

        bs = K.shape(self.x)[0]
        ks = K.shape(self.kernel)

        tmp_mask = tf.gather(tf.constant(self._mask), K.reshape(self._state,[-1]))
        masked = tf.multiply(K.tile(K.reshape(self.kernel,[1,ks[0],ks[1]]),[bs,1,1]), tmp_mask)
        self._output = tf.matmul(K.reshape(self.x,[bs,1,ks[0]]), masked)
        return self._activation(K.reshape(self._output,[bs,self.output_dim]))
  
    def compute_output_shape(self, input_shape):
        return (input_shape[0][0], self.output_dim)

def generate_all_masks(num_of_all_masks, num_of_hlayer, hlayer_size, graph_size, algo, min_related_nodes):
        
    all_masks = []
    for i in range(0,num_of_all_masks):
        #generating subsets as 3d matrix 
        #subsets = np.random.randint(0, 2, (num_of_hlayer, hlayer_size, graph_size))

        labels = np.zeros([num_of_hlayer, hlayer_size], dtype=np.float32)
        min_label = 0
        for ii in range(num_of_hlayer):
            labels[ii][:] = np.random.randint(min_label, graph_size, (hlayer_size))
            min_label = np.amin(labels[ii])
        #generating masks as 3d matrix
        #masks = np.zeros([num_of_hlayer,hlayer_size,hlayer_size])
        
        masks = []
#        if (algo == 'orig'):
#            pi = np.random.permutation(graph_size)
#            #pi = np.array(range(graph_size))
#        else:
#            pi = np.array(range(graph_size))
        #first layer mask
        mask = np.zeros([graph_size, hlayer_size], dtype=np.float32)
        for j in range(0, hlayer_size):
            for k in range(0, graph_size):
                if (algo == 'orig'):
                    if (labels[0][j] >= k): 
                        mask[k][j] = 1.0
                else:
                    if ((labels[0][j] >= k) and 
                        (min_related_nodes[int(labels[0][j])] <= k)):  #cant use permutation in our approach
                        mask[k][j] = 1.0
        masks.append(mask)
        
        #hidden layers mask   
        for i in range(1, num_of_hlayer):
            mask = np.zeros([hlayer_size, hlayer_size], dtype=np.float32)
            for j in range(0, hlayer_size):
                for k in range(0, hlayer_size):
                    if (algo == 'orig'):
                        if (labels[i][j] >= labels[i-1][k]): 
                            mask[k][j] = 1.0
                    else:
                        if ((labels[i][j] >= labels[i-1][k]) and 
                            (min_related_nodes[int(labels[i][j])] <= labels[i-1][k])):
                            mask[k][j] = 1.0
            masks.append(mask)
        
        #last layer mask
        mask = np.zeros([hlayer_size, graph_size], dtype=np.float32)
        #last_layer_label = np.random.randint(0, 4, graph_size)
        for j in range(0, graph_size):
            for k in range(0, hlayer_size):
                if (algo == 'orig'):
                    if (j > labels[-1][k]): 
                        mask[k][j] = 1.0
                else:
                    if (j > labels[-1][k]) and (min_related_nodes[j] <= labels[-1][k]): 
                        mask[k][j] = 1.0
        masks.append(mask)
        all_masks.append(masks)
        
    swapped_all_masks = []
    for i in range(num_of_hlayer+1):
        swapped_masks = []
        for j in range(num_of_all_masks):
            swapped_masks.append(all_masks[j][i])
        swapped_all_masks.append(swapped_masks)
        
    #all_masks = [[x*1.0 for x in y] for y in all_masks]
    
    return swapped_all_masks

def main():
    
    #parameter setup
    graph_size = int(sys.argv[1])
    train_length = int(sys.argv[2])
    valid_length = int(sys.argv[3])
    test_length = int(sys.argv[4])
    algorithm = sys.argv[5]
    print ('algorithm', algorithm)  #original or minus-width for now
    
    np.random.seed(4125) 
    AE_adam = optimizers.Adam(lr=0.03, beta_1=0.1)
    num_of_exec = 5
    num_of_all_masks = 10
    num_of_hlayer = 2
    hlayer_size = 20
    fit_iter = 1
    num_of_epochs = 2000   #max number of epoch if not reaches the ES condition
    batch_s = 50
    optimizer = AE_adam
    patience = 20
    test_digit=1
    
    with np.load('modelinfo/asia_modelinfo.npz') as model:
        min_related_nodes = model['min_related_nodes']
        
    with np.load('datasets/asia.npz') as dataset:
        data = np.copy(dataset['train_data'])
        np.random.shuffle(data)
        train_data = data[0:train_length][:]
        np.random.shuffle(data)
        valid_data = data[0:valid_length][:]
        data = np.copy(dataset['test_data'])
        np.random.shuffle(data)
        test_data = data[0:test_length][:]
        
    NLLs = []            
    results = []
    start_time = time.time()
    for ne in range(0, num_of_exec):                      
        all_masks = generate_all_masks(num_of_all_masks, num_of_hlayer, hlayer_size, graph_size, algorithm, min_related_nodes)
#        perm_matrix = np.zeros((test_length, graph_size))
#        for i in range(test_length):
#            for j in range(graph_size):
#                perm_matrix[i][j] = test_data[i][np.where(pi==j)[0][0]]
            #perm_matrix[i][j] = test_data[i][k]  :  pi[k] == j

        
        input_layer = Input(shape=(graph_size,))
        state = Input(shape=(1,), dtype = "int32")

        if (num_of_hlayer == 2): 
            mask_1 = Input(shape = (graph_size , hlayer_size))
            mask_2 = Input(shape = (hlayer_size , hlayer_size))
            mask_3 = Input(shape = (hlayer_size , graph_size))
        else:
            mask_1 = Input(shape = (graph_size , hlayer_size))
            mask_2 = Input(shape = (hlayer_size , hlayer_size))
            mask_3 = Input(shape = (hlayer_size , hlayer_size))
            mask_4 = Input(shape = (hlayer_size , hlayer_size))
            mask_5 = Input(shape = (hlayer_size , hlayer_size))
            mask_6 = Input(shape = (hlayer_size , hlayer_size))
            mask_7 = Input(shape = (hlayer_size , graph_size))
    
        if (num_of_hlayer == 2):
            hlayer1 = MaskedDenseLayer(hlayer_size, np.array(all_masks[0]), 'relu')( [input_layer, state] )
            hlayer2 = MaskedDenseLayer(hlayer_size, np.array(all_masks[1]), 'relu')( [hlayer1, state] )
            output_layer = MaskedDenseLayer(graph_size, np.array(all_masks[2]), 'sigmoid')( [hlayer2, state] )
        else:
            hlayer1 = MaskedDenseLayer(hlayer_size, np.array(all_masks[0]), 'relu')( [input_layer, state] )
            hlayer2 = MaskedDenseLayer(hlayer_size, np.array(all_masks[1]), 'relu')( [hlayer1, state] )
            hlayer3 = MaskedDenseLayer(hlayer_size, np.array(all_masks[2]), 'relu')( [hlayer2, state] )
            hlayer4 = MaskedDenseLayer(hlayer_size, np.array(all_masks[3]), 'relu')( [hlayer3, state] )
            hlayer5 = MaskedDenseLayer(hlayer_size, np.array(all_masks[4]), 'relu')( [hlayer4, state] )
            hlayer6 = MaskedDenseLayer(hlayer_size, np.array(all_masks[5]), 'relu')( [hlayer5, state] )
            output_layer = MaskedDenseLayer(graph_size, np.array(all_masks[6]), 'sigmoid')( [hlayer6, state] )
        if (num_of_hlayer == 6):
            autoencoder = Model(inputs=[input_layer, state], outputs=[output_layer])
        else:
            autoencoder = Model(inputs=[input_layer, state], outputs=[output_layer])
        
        autoencoder.compile(optimizer=optimizer, loss='binary_crossentropy')
        #reassign_mask = ReassignMask()
        early_stop = MyEarlyStopping(monitor='val_loss', min_delta=0, patience=patience, verbose=1, mode='auto')
        
        reped_state_train = np.arange(train_length*num_of_all_masks, dtype=np.int32)/train_length
        reped_state_valid = np.arange(valid_length*num_of_all_masks, dtype=np.int32)/valid_length
        reped_traindata = np.tile(train_data, [num_of_all_masks, 1])
        reped_validdata = np.tile(valid_data, [num_of_all_masks, 1])
                
        for i in range(0, fit_iter):
            if (num_of_hlayer == 6):
                autoencoder.fit(x=[reped_traindata, reped_state_train],
                                  y=[reped_traindata],
                                  epochs=num_of_epochs,
                                  batch_size=batch_s,
                                  shuffle=True,
                                  validation_data=([reped_validdata, reped_state_valid],
                                                    [reped_validdata]),
                                  callbacks=[early_stop],
                                  verbose=1)
            else:
                autoencoder.fit(x=[reped_traindata, 
                                  reped_state_train],
                                  y=[reped_traindata],
                                  epochs=num_of_epochs,
                                  batch_size=batch_s,
                                  shuffle=True,
                                  validation_data=([reped_validdata, reped_state_valid],
                                                    [reped_validdata]),
                                  callbacks=[early_stop],
                                  verbose=1)

        #reped_testdata = np.tile(test_data, [num_of_all_masks, 1])
        made_probs = np.zeros([num_of_all_masks, test_length], dtype=np.float32)
        for j in range(num_of_all_masks):
            made_predict = autoencoder.predict([test_data, j * np.ones([test_length,1])])#.reshape(1, hlayer_size, graph_size)]
            made_predict[made_predict==0.0] = np.nextafter(np.float32(0), np.float32(1))
            #made_predicts.append(made_predict)
#            corrected_probs = np.multiply(np.power(made_predict, test_data), 
#                            np.power(np.ones(made_predict.shape) - made_predict, np.ones(test_data.shape) - test_data))
            corrected_probs = np.multiply(test_data, np.log(made_predict))
            + np.multiply( (np.ones(test_data.shape) - test_data) , np.log(np.ones(made_predict.shape) - made_predict))
            made_prob = np.sum(corrected_probs, 1)
            made_probs[j][:] = made_prob
        
        a_m = np.max(made_probs, axis=0)
        diffsumexp = made_probs - np.tile(a_m, [num_of_all_masks,1])
        all_avg_probs = np.log(np.ones(test_length)/test_length) + a_m
        + np.log(np.sum(np.exp(diffsumexp), axis=0))
#        all_avg_probs = np.mean(made_probs, axis=0)
        results.append(all_avg_probs)
        NLL = -1*np.mean(all_avg_probs)
        NLLs.append(NLL)
        #print('made_probs', made_probs)
        #print('test_probs', test_data_probs)
        #tmp = made_probs  train_data_probs
    model_json = autoencoder.to_json()
    with open("mnist/model.json", "w") as json_file:
        json_file.write(model_json)
    # serialize weights to HDF5
    model_path = 'mnist/model_' + algorithm + '.h5'
    autoencoder.save_weights(model_path)
    print("Saved model to disk")
    
    results_path = 'mnist/mnist_' + algorithm + '_results'
    np.savez(results_path, results=results)
    mean_NLLs = sum(NLLs)/num_of_exec
    variance_NLLs = 1.0/len(NLLs) * np.sum(np.square([x - mean_NLLs for x in NLLs]))
    #mean_KLs = sum(KLs)/num_of_exec
    #variance_KLs = 1.0/len(KLs) * np.sum(np.square([x - mean_KLs for x in KLs]))

    total_time = time.time() - start_time
    global train_end_epochs
    print('End Epochs:', train_end_epochs)
    print('End Epochs Average', np.mean(train_end_epochs))
    print('AVG NLL:', mean_NLLs)
    print('var NLL:', variance_NLLs)
    print('Total Time:', total_time)

if __name__=='__main__':
    main()
