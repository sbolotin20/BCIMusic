"""BCI Helper"""

# imports
import math
import os
import sys
from tempfile import gettempdir
from subprocess import call
import matplotlib.pyplot as plt
import numpy as np
from sklearn import svm
from sklearn.ensemble import RandomForestClassifier
from scipy.signal import butter, lfilter, lfilter_zi
from pylsl import StreamInlet, resolve_byprop  # Module to receive EEG data

# -*- coding: utf-8 -*-

# initialize notches for bandpass filter
NOTCH_B, NOTCH_A = butter(4, np.array([55, 65])/(256/2), btype='bandstop')

def record_eeg(r_length, freq, channel_i):
	streams = resolve_byprop('type', 'EEG', timeout=2)

	inlet  = StreamInlet(streams[0], max_chunklen=12)
	""" Records EEG data from headset

	Arguments:

	r_length  -- how many seconds of data to record
	freq      -- sample rate
	channel_i -- channels to keep data from

	Returns:

	data      -- array of recorded data [sample, channel]

	"""

	data, timestamps = inlet.pull_chunk( 
		timeout = r_length + 1, 
		max_samples = int(freq * r_length))

	data = np.array(data)[:, channel_i]

	return data


def update_buffer(data_buffer, new_data, notch = False, filter_state = None):
    """ Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop 

	Updates the buffer with new data and applies butterworth filter

	Arguments:

	buffer       -- array for eeg data buffer [samples][channels]
	new_data     -- array with new data from channel [samples][channels]
	apply_filter -- (Boolean) when True, apply filter to buffer
	filter_state -- array of filtered values

	Returns:

	new_buffer   -- array of updated buffer [samples][channels]

	"""
	
    if new_data.ndim == 1:

        new_data = new_data.reshape(-1, data_buffer.shape[1])
	
    if notch:
        if filter_state is None:
            filter_state = np.tile(lfilter_zi(NOTCH_B, NOTCH_A),
                                   (data_buffer.shape[1], 1)).T
        
        new_data, filter_state = lfilter(NOTCH_B, NOTCH_A, new_data, axis=0,
                                         zi = filter_state)

    new_buffer = np.concatenate((data_buffer, new_data), axis=0)
    new_buffer = new_buffer[new_data.shape[0]:, :]

    return new_buffer, filter_state



def epoch_array(eeg_data, epoch_length, overlap_length, freq):
	""" Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop """

	""" Divides eeg data into epochs of specified length

	Arguments:

	eeg_data  -- 2D array of eeg_data [samples, channels]
	n_samples -- number of samples for each epoch (int)
	overlap   -- number of samples that overlap from previous epoch
	freq      -- sample rate

	Returns:

	epochs    -- 3D array of epochs [epoch_samples, channels, epochs]



	"""
	freq = np.abs(freq)

	n_total_samples, n_channels = eeg_data.shape

	# convert seconds to number of samples
	epoch_n_samples   = epoch_length * freq
	overlap_n_samples = 0#overlap_length * freq
	shift_n_samples  = epoch_n_samples - overlap_n_samples

	# total number of epochs
	n_epochs = int(np.floor((n_total_samples - epoch_n_samples)
	/ float(shift_n_samples)) + 1)

	# markers to indicate where epochs start and how many samples per epoch
	markers = np.asarray(range(0, n_epochs + 1)) * shift_n_samples
	markers = markers.astype(int)

	# initialize array to hold epoch data
	epochs = np.zeros((epoch_n_samples, n_channels, n_epochs))

	# divide eeg_data into epochs
	for i in range(0, n_epochs):
		epochs[:,:,i] = eeg_data[markers[i]:markers[i] + epoch_n_samples, :]

		return epochs


def get_last_data(eeg_buffer, n_samples):
	""" Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop """
	""" Grabs latest data from buffer

	Arguments:
d
	eeg_buffer -- array of raw eeg data [samples][channels]
	n_samples  -- number of samples to to pull from buffer

	Returns:

	last_data -- array that holds latest data [values]

	"""

	last_data = eeg_buffer[(eeg_buffer.shape[0] - n_samples):, :]

	return last_data


def next_pow_2(x):
	""" Gets the next power of two greater than x.

	Arguments:

	x -- input value

	Returns:

	y -- next power of 2

	"""

	n = 1
	while n < x:
		n = n * 2
	return n



def compute_band_powers(epoch, freq):
	""" Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop """

	""" Computes band powers as feature matrix from epoch

	Arguments:

	epoch       -- 2D array of epoch data [samples, channels]
	freq        -- (float) sample rate

	Returns:

	band_powers --  2D array containing features
	--  [feature values, different features (delta, theta etc...)]
	"""

	sample_length, n_channels = epoch.shape

	# Hammming Window
	hwin            = np.hamming(sample_length)
	data_centered   = epoch - np.mean(epoch, axis=0)
	h_data_centered = (data_centered.T * hwin).T

	# length of axis for FFT output
	n_axis = next_pow_2(sample_length)

	# compute one-dimensional FFT
	fastFT = np.fft.fft(h_data_centered, n = n_axis, axis = 0) / sample_length

	# compute Power Spectral Density (true theoretical FFT)
	PSD = 2 * np.abs(fastFT[0:int(n_axis / 2), :])

	# frequency bins so separate features
	freq_bin = freq / 2 * np.linspace(0, 1, int(n_axis / 2))


	# Separate band powers and take mean for the epoch
	# Delta < 4
	delta_index, = np.where(freq_bin < 4)
	meanDelta    = np.mean(PSD[delta_index, :], axis=0)

	# Theta 4-8
	theta_index, = np.where((freq_bin >= 4) & (freq_bin <= 8))
	meanTheta    = np.mean(PSD[theta_index, :], axis=0)

	# Alpha 8-12
	alpha_index, = np.where((freq_bin >= 8) & (freq_bin <= 12))
	meanAlpha    = np.mean(PSD[alpha_index, :], axis=0)

	# Beta 12-30
	beta_index,  = np.where((freq_bin >= 12) & (freq_bin < 30))
	meanBeta     = np.mean(PSD[beta_index, :], axis=0)

	band_powers  = np.concatenate((meanDelta, meanTheta,
	meanAlpha, meanBeta), axis=0)
	band_powers  = np.log10(band_powers)

	return band_powers


def compute_feature_matrix(epochs, freq):
	""" Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop """
	""" Computes band powers for multiple epochs

	Arguments:

	epochs         -- 3D array of epochs [epoch_samples, channels, epochs]
	freq           -- (float)sample rate

	Returns:

	feature_matrix -- matrix of epochs and corresponding features
	-- [epochs][band powers]
	"""

	n_epochs = epochs.shape[2]

	# call compute_band_powers for each epoch
	for epoch in range(n_epochs):
		# first epoch initialze matrix
		if epoch == 0:
			feat           = compute_band_powers(epochs[:, :, epoch], freq).T
			feature_matrix = np.zeros((n_epochs, feat.shape[0]))

			feature_matrix[epoch, :] = compute_band_powers(
			epochs[:, :, epoch], freq).T

			return feature_matrix


def train_classifier(feature_m0, feature_m1, feature_m2, feature_m3,
algorithm = 'RandomForestClassifier'):
	""" Trains a random forest classifier from 4 different feature matrices

	Arguments:

	feature_m0 -- feature matrix [epochs][band powers]
	feature_m1 -- feature matrix [epochs][band powers]
	feature_m2 -- feature matrix [epochs][band powers]
	feature_m3 -- feature matrix [epochs][band powers]
	algorithm  -- (str) type of algorithm to use

	Returns:

	clf        -- (sklean object) RandomForestClassifer
	mu_ft	   -- array that holds normalization mean
	std_ft	   -- array that holds the nomralisation standard deviation
	score 	   -- accuracy of model

	"""

	# Create vector Y (class labels)
	class0 = np.zeros((feature_m0.shape[0], 1))
	class1 = np.ones((feature_m1.shape[0], 1))
	class2 = np.full((feature_m2.shape[0], 1), fill_value = 2)
	class3 = np.full((feature_m3.shape[0], 1), fill_value = 3)


	# Concatenate class labels
	y = np.concatenate((class0, class1, class2, class3), axis=0)

	# Concatenate feature matrices
	features_all = np.concatenate((feature_m0,
	feature_m1,
	feature_m2,
	feature_m3),
	axis=0)

	# Normalize features columnwise
	mu_ft  = np.mean(features_all, axis=0)
	std_ft = np.std(features_all, axis=0)
	X      = (features_all - mu_ft) / std_ft

	# Train RandomForestclassifier using default parameters
	clf = RandomForestClassifier()
	clf.fit(X,y)
	score = clf.score(X, y.ravel())

	return clf, mu_ft, std_ft, score


def test_classifier(clf, feat_vector, mu_ft, std_ft):
	""" Title: BCI Workshop Auxiliary Tools
	Author: Cassani
	Date: May 08 2015
	Availability: https://github.com/NeuroTechX/bci-workshop """
	""" Test the classifier on new data points.

	Arguments:
	clf         -- (sklean object) RandomForestClassifer
	feat_vector -- array of features [samples][features]
	mu_ft	    -- array that holds normalization mean
	std_ft	    -- array that holds the normalization standard deviation

	Returns:
	y_hat       -- decision of the classifier on data points
	"""

	# Normalize feature_vector
	x     = (feat_vector - mu_ft) / std_ft
	y_hat = clf.predict(x)

	return y_hat

class DataPlotter():
    """
    Class for creating and updating a line plot.
    """

    def __init__(self, nbPoints, chNames, fs=None, title=None):
        """Initialize the figure."""

        self.nbPoints = nbPoints
        self.chNames = chNames
        self.nbCh = len(self.chNames)

        self.fs = 1 if fs is None else fs
        self.figTitle = '' if title is None else title

        data = np.empty((self.nbPoints, 1))*np.nan
        self.t = np.arange(data.shape[0])/float(self.fs)

        # Create offset parameters for plotting multiple signals
        self.yAxisRange = 100
        self.chRange = self.yAxisRange/float(self.nbCh)
        self.offsets = np.round((np.arange(self.nbCh)+0.5)*(self.chRange))

        # Create the figure and axis
        plt.ion()
        self.fig, self.ax = plt.subplots()
        self.ax.set_yticks(self.offsets)
        self.ax.set_yticklabels(self.chNames)

        # Initialize the figure
        self.ax.set_title(self.figTitle)

        self.chLinesDict = {}
        for i, chName in enumerate(self.chNames):
            self.chLinesDict[chName], = self.ax.plot(
                    self.t, data+self.offsets[i], label=chName)

        self.ax.set_xlabel('Time')
        self.ax.set_ylim([0, self.yAxisRange])
        self.ax.set_xlim([np.min(self.t), np.max(self.t)])

        plt.show()

    def update_plot(self, data):
        """ Update the plot """

        data = data - np.mean(data, axis=0)
        std_data = np.std(data, axis=0)
        std_data[np.where(std_data == 0)] = 1
        data = data/std_data*self.chRange/5.0

        for i, chName in enumerate(self.chNames):
            self.chLinesDict[chName].set_ydata(data[:, i] + self.offsets[i])

        self.fig.canvas.draw()

    def clear(self):
        """ Clear the figure """

        blankData = np.empty((self.nbPoints, 1))*np.nan

        for i, chName in enumerate(self.chNames):
            self.chLinesDict[chName].set_ydata(blankData)

        self.fig.canvas.draw()

    def close(self):
        """ Close the figure """

        plt.close(self.fig)

def calculateArousal(epoch, freq):
	# arousal = meanBeta / meanAlpha
	sample_length, n_channels = epoch.shape

	# length of axis for FFT output
	n_axis = next_pow_2(sample_length)

	# frequency bins so separate features
	freq_bin = freq / 2 * np.linspace(0, 1, int(n_axis / 2))

	# Alpha 8-12
	alpha_index, = np.where((freq_bin >= 8) & (freq_bin <= 12))
	meanAlpha    = np.mean(PSD[alpha_index, :], axis=0)

	# Beta 12-30
	beta_index,  = np.where((freq_bin >= 12) & (freq_bin < 30))
	meanBeta     = np.mean(PSD[beta_index, :], axis=0)

	return meanBeta/meanAlpha
	
def calculateValence(epoch, freq, electrodeRight, electrodeLeft):
	# valence = alphaRIGHT/betaRIGHT - alphaLEFT/betaLEFT
	sample_length, n_channels = epoch.shape
	# length of axis for FFT output
	n_axis = next_pow_2(sample_length)

	# frequency bins so separate features
	freq_bin = freq / 2 * np.linspace(0, 1, int(n_axis / 2))
	'''
		somehow need to incorporate different
		electrodes to calculate 4 vars
		For left vs  right u want to look 
		at electrodes on the left vs right
	(so AF7 vs AF8) I think
	'''
	alphaRight_index, = np.where((freq_bin >= 4) & (freq_bin <= 12))
	alphaRight  = np.mean(PSD[alphaRight_index, :], axis=0)

	alphaLeft_index, = np.where((freq_bin >= 4) & (freq_bin <= 12))
	alphaLeft  = np.mean(PSD[alphaLeft_index, :], axis=0)

	betaRight_index, = np.where((freq_bin >= 13) & (freq_bin <= 30))
	betaRight  = np.mean(PSD[betaRight_index, :], axis=0)

	betaLeft_index, = np.where((freq_bin >= 13) & (freq_bin <= 30))
	betaLeft  = np.mean(PSD[betaLeft_index, :], axis=0)

	return (alphaRight/betaRight)-(alphaLeft/ betaLeft)

def generateNewNote(epoch, freq, electrodeRight, electrodeLeft):
	# have one epoch and can select only one
	# electrode within that epoch
	# (one row in the array). The data I
	# think is a 2d array with number of 
	# electrodes x time points, so to choose just
	# one electrode you would use just one row.
	valence = calculateValence(epoch, freq, electrodeRight, electrodeLeft)
	arousal = calculateArousal(epoch, freq)


	# imagine unit circle given radius 10

	# high valence, high arousal (0-10 for each)
	# low valence, high arousal (-10-0 V, 0-10 A)
	# high valence, low arousal (0-10 V, -10-0 A)
	# low valence, low arousal (-10-0 for each)

	# if valence is negative add pi 
	if (valence < 0):
		angle = math.atan(valence/arousal) + math.pi
	else:
		angle = math.atan(valence/arousal)

	math.degrees(angle)

	# first quadrant 
	if (angle > 0 & angle <= 30):
		emotion = "pleased"
	if (angle > 30 & angle <= 60):
		emotion = "happy"
	if (angle > 60 & angle <= 90):
		emotion = "excited"

	# second quadrant 
	if (angle > 90 & angle <= 120):
		emotion = "annoyed"
	if (angle > 120 & angle <= 150):
		emotion - "angry"
	if (angle > 150 & angle <= 180):
		emotion = "nervous"

	# third quadrant 
	if (angle > 180 & angle <= 210):
		emotion = "sad"
	if (angle > 210 & angle <= 240):
		emotion - "bored"
	if (angle > 240 & angle <= 270):
		emotion = "sleepy"

	# fourth quadrant 
	if (angle <= 0 & angle >= -30):
		emotion = "relaxed"
	if (angle < -30 & angle >= -60):
		emotion = "peaceful"
	if (angle < -60 & angle >= -90):
<<<<<<< HEAD
		emotion = "calm"
=======
		emotion = "calm"
>>>>>>> 98f350c5729a4f1bc6d66296613a490d364ab116
