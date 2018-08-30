import os
import sys
import ast
import time
import string
import locale
import pathlib
import warnings
import numpy as np
import pandas as pd
from collections import OrderedDict

# Turn off warnings by default
if not sys.warnoptions:
    warnings.simplefilter("ignore")

from sklearn import preprocessing
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA, KernelPCA, IncrementalPCA, TruncatedSVD

from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import AdaBoostClassifier, AdaBoostRegressor, BaggingClassifier,\
                             BaggingRegressor, ExtraTreesClassifier, ExtraTreesRegressor,\
                             GradientBoostingClassifier, GradientBoostingRegressor,\
                             RandomForestClassifier, RandomForestRegressor, VotingClassifier
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, LogisticRegressionCV,\
                                 PassiveAggressiveClassifier, PassiveAggressiveRegressor,\
                                 Perceptron, RANSACRegressor, Ridge, RidgeClassifier, RidgeCV,\
                                 RidgeClassifierCV, SGDClassifier, SGDRegressor, TheilSenRegressor
from sklearn.naive_bayes import BernoulliNB, GaussianNB, MultinomialNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor, RadiusNeighborsClassifier,\
                              RadiusNeighborsRegressor
from sklearn.neural_network import BernoulliRBM, MLPClassifier, MLPRegressor
from sklearn.svm import LinearSVC, LinearSVR, NuSVC, NuSVR, SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, ExtraTreeClassifier,\
                         ExtraTreeRegressor

import _utils as utils
from _machine_learning import Preprocessor, PersistentModel
import ServerSideExtension_pb2 as SSE

# Add Generated folder to module path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PARENT_DIR, 'generated'))

class SKLearnForQlik:
    """
    A class to implement scikit-learn classification and regression algorithmns for Qlik.
    http://scikit-learn.org/stable/modules/classes.html#api-reference
    """
    
    # Counter used to name log files for instances of the class
    log_no = 0
    
    # Ordered Dictionary to cache recently used models at the class level
    model_cache = OrderedDict()
    
    # Limit on the number of models to be cached
    cache_limit = 3
    
    def __init__(self, request, context, path="../models/"):
        """
        Class initializer.
        :param request: an iterable sequence of RowData
        :param context:
        :param path: a directory path to store persistent models
        :Sets up the model parameters based on the request
        """
               
        # Set the request, context and path variables for this object instance
        self.request = request
        self.context = context
        self.path = path
        self.logfile = None
        
        # Set up a dictionary of valid algorithmns
        self.algorithms = {"DummyClassifier":DummyClassifier, "DummyRegressor":DummyRegressor,\
                           "AdaBoostClassifier":AdaBoostClassifier, "AdaBoostRegressor":AdaBoostRegressor,\
                           "BaggingClassifier":BaggingClassifier, "BaggingRegressor":BaggingRegressor,\
                           "ExtraTreesClassifier":ExtraTreesClassifier, "ExtraTreesRegressor":ExtraTreesRegressor,\
                           "GradientBoostingClassifier":GradientBoostingClassifier,\
                           "GradientBoostingRegressor":GradientBoostingRegressor,\
                           "RandomForestClassifier":RandomForestClassifier, "RandomForestRegressor":RandomForestRegressor,\
                           "VotingClassifier":VotingClassifier, "GaussianProcessClassifier":GaussianProcessClassifier,\
                           "GaussianProcessRegressor":GaussianProcessRegressor, "LinearRegression":LinearRegression,\
                           "LogisticRegression":LogisticRegression, "LogisticRegressionCV":LogisticRegressionCV,\
                           "PassiveAggressiveClassifier":PassiveAggressiveClassifier,\
                           "PassiveAggressiveRegressor":PassiveAggressiveRegressor, "Perceptron":Perceptron,\
                           "RANSACRegressor":RANSACRegressor, "Ridge":Ridge, "RidgeClassifier":RidgeClassifier,\
                           "RidgeCV":RidgeCV, "RidgeClassifierCV":RidgeClassifierCV, "SGDClassifier":SGDClassifier,\
                           "SGDRegressor":SGDRegressor, "TheilSenRegressor":TheilSenRegressor, "BernoulliNB":BernoulliNB,\
                           "GaussianNB":GaussianNB, "MultinomialNB":MultinomialNB,\
                           "KNeighborsClassifier":KNeighborsClassifier, "KNeighborsRegressor":KNeighborsRegressor,\
                           "RadiusNeighborsClassifier":RadiusNeighborsClassifier,\
                           "RadiusNeighborsRegressor":RadiusNeighborsRegressor, "BernoulliRBM":BernoulliRBM,\
                           "MLPClassifier":MLPClassifier, "MLPRegressor":MLPRegressor, "LinearSVC":LinearSVC,\
                           "LinearSVR":LinearSVR, "NuSVC":NuSVC, "NuSVR":NuSVR, "SVC":SVC, "SVR":SVR,\
                           "DecisionTreeClassifier":DecisionTreeClassifier, "DecisionTreeRegressor":DecisionTreeRegressor,\
                           "ExtraTreeClassifier":ExtraTreeClassifier, "ExtraTreeRegressor":ExtraTreeRegressor}
        
        self.decomposers = {"PCA":PCA, "KernelPCA":KernelPCA, "IncrementalPCA":IncrementalPCA, "TruncatedSVD":TruncatedSVD}
        
    def list_models(self):
        """
        List available models.
        This function is only meant to be used as a chart expression in Qlik.
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData']
        col_headers = ['search_pattern']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
        
        # Get the list of models based on the search pattern
        search_pattern = self.request_df.loc[0, 'search_pattern']
        
        # If the search pattern is empty default to all models
        if not search_pattern.strip():
            search_pattern = '*'
        
        # Get the list of models as a string
        models = ", ".join([str(p).split("\\")[-1] for p in list(pathlib.Path(self.path).glob(search_pattern))])
        
        # Prepare the output
        self.response = pd.Series(models)
        
        # Finally send the response
        return self.response
    
    def setup(self, dim_reduction=False):
        """
        Initialize the model with given parameters
        Arguments are retreived from the keyword argument columns in the request data
        Arguments should take the form of a comma separated string: 'arg1=value1, arg2=value2'
        For estimater, scaler and dimensionality reduction hyperparameters the type should also be specified
        Use the pipe | character to specify type: 'arg1=value1|str, arg2=value2|int, arg3=value3|bool' 
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData', 'strData', 'strData', 'strData']
        col_headers = ['model_name', 'estimator_args', 'scaler_args', 'execution_args']
        
        if dim_reduction:
            # If specified, get dimensionality reduction arguments
            row_template = ['strData', 'strData', 'strData', 'strData', 'strData']
            col_headers = ['model_name', 'estimator_args', 'scaler_args', 'dim_reduction_args', 'execution_args']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
               
        # Create a model that can be persisted to disk
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the argument strings from the request dataframe
        estimator_args = self.request_df.loc[0, 'estimator_args']
        scaler_args = self.request_df.loc[0, 'scaler_args']
        execution_args = self.request_df.loc[0, 'execution_args']
        if dim_reduction:
            dim_reduction_args = self.request_df.loc[0, 'dim_reduction_args']
        
        # Set the relevant parameters using the argument strings
        if dim_reduction:
            self._set_params(estimator_args, scaler_args, execution_args, dim_reduction_args=dim_reduction_args)
            self.model.dim_reduction = True
        else:
            self._set_params(estimator_args, scaler_args, execution_args)
            self.model.dim_reduction = False
        
        # Persist the model to disk
        self.model = self.model.save(self.model.name, self.path, self.model.compress)
        
        # Update the cache to keep this model in memory
        self._update_cache()
              
        # Prepare the output
        message = [[self.model.name, 'Model successfully saved to disk',\
                    time.strftime('%X %x %Z', time.localtime(self.model.state_timestamp))]]
        self.response = pd.DataFrame(message, columns=['model_name', 'result', 'time_stamp'])
        
        # Send the reponse table description to Qlik
        self._send_table_description("setup")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(4)
        
        # Finally send the response
        return self.response
    
    def set_features(self):
        """
        Add feature definitions for the model
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData', 'strData', 'strData', 'strData', 'strData', 'numData']
        col_headers = ['model_name', 'name', 'variable_type', 'data_type', 'feature_strategy', 'hash_features']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
       
        # Initialize the persistent model
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the model from cache or disk
        self._get_model()
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(3)
        
        # Add the feature definitions to the model
        self.model.features_df = self.request_df
        self.model.features_df.set_index("name", drop=False, inplace=True)
               
        # Persist the model to disk
        self.model = self.model.save(self.model.name, self.path, self.model.compress)
        
        # Update the cache to keep this model in memory
        self._update_cache()
        
        # Prepare the output
        message = [[self.model.name, 'Feature definitions successfully saved to model',\
                    time.strftime('%X %x %Z', time.localtime(self.model.state_timestamp))]]
        self.response = pd.DataFrame(message, columns=['model_name', 'result', 'time_stamp'])
        
        # Send the reponse table description to Qlik
        self._send_table_description("setup")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(4)
        
        # Finally send the response
        return self.response
    
    def get_features(self):
        """
        Get feature definitions for an existing model
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData']
        col_headers = ['model_name']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
        
        # Initialize the persistent model
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the model from cache or disk
        self._get_model()
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(3)
        
        # Prepare the output
        self.response = self.model.features_df
        self.response["sort_order"] = pd.Series([i+1 for i in range(len(self.response.index))], index=self.response.index)
        self.response = self.response[["model_name", "sort_order", "name", "variable_type", "data_type",\
                                       "feature_strategy", "hash_features"]]
        
        # Send the reponse table description to Qlik
        self._send_table_description("features")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(4)
        
        # Finally send the response
        return self.response
        
    def fit(self):
        """
        Train and test the model based on the provided dataset
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData', 'strData']
        col_headers = ['model_name', 'n_features']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
        
        # Initialize the persistent model
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the model from cache or disk
        self._get_model()
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(3)
        
        # Split the features provided as a string into individual columns
        train_test_df = pd.DataFrame([x[1].split("|") for x in self.request_df.values.tolist()],\
                                     columns=self.model.features_df.loc[:,"name"].tolist(),\
                                     index=self.request_df.index)
        
        # Convert the data types based on feature definitions 
        train_test_df = utils.convert_types(train_test_df, self.model.features_df)
        
        # Get the target feature
        # NOTE: This code block will need to be reviewed for multi-label classification
        target = self.model.features_df.loc[self.model.features_df["variable_type"] == "target"]
        target_name = target.index[0]

        # Get the target data
        target_df = train_test_df.loc[:,[target_name]]

        # Get the features to be excluded from the model
        exclusions = self.model.features_df['variable_type'].isin(["excluded", "target", "identifier"])
        
        # Update the feature definitions dataframe
        excluded = self.model.features_df.loc[exclusions]
        self.model.features_df = self.model.features_df.loc[~exclusions]
        
        # Remove excluded features from the data
        train_test_df = train_test_df[self.model.features_df.index.tolist()]
        
        # Split the data into training and testing subsets
        self.X_train, self.X_test, self.y_train, self.y_test = \
        train_test_split(train_test_df, target_df, test_size=self.model.test_size, random_state=self.model.random_state)
        
        # Add the training and test data to the model if required
        if self.model.retain_data:
            self.model.X_train = self.X_train
            self.model.X_test = self.X_test
            self.model.y_train = self.y_train
            self.model.y_test = self.y_test
        
        # Construct the preprocessor
        prep = Preprocessor(self.model.features_df, scale_hashed=self.model.scale_hashed, missing=self.model.missing,\
                            scaler=self.model.scaler, **self.model.scaler_kwargs)
        
        # Construct an estimator
        estimator = self.algorithms[self.model.estimator](**self.model.estimator_kwargs)
        
        # Construct a sklearn pipeline
        self.model.pipe = Pipeline([('preprocessor', prep), ('estimator', estimator)])
        self.model.estimation_step = 1
        
        if self.model.dim_reduction:
            # Construct the dimensionality reduction object
            reduction = self.decomposers[self.model.reduction](**self.model.dim_reduction_kwargs)
            
            # Include dimensionality reduction in the sklearn pipeline
            self.model.pipe = self.model.pipe.insert(1, ('reduction', reduction))
            self.model.estimation_step = 2
        
        # Fit the training data to the pipeline
        self.model.pipe.fit(self.X_train, self.y_train.values.ravel())
        
        # Test the accuracy of the model using the test data
        self.model.score = self.model.pipe.score(self.X_test, self.y_test)
        
        # Persist the model to disk
        self.model = self.model.save(self.model.name, self.path, self.model.compress)
        
        # Update the cache to keep this model in memory
        self._update_cache()
        
        # Prepare the output
        message = [[self.model.name, 'Model successfully trained, tested and saved to disk.',\
                    time.strftime('%X %x %Z', time.localtime(self.model.state_timestamp)),\
                    "{0} model has a {1:.3f} accuracy against the test data."\
                    .format(self.model.estimator, self.model.score), self.model.score]]
        self.response = pd.DataFrame(message, columns=['model_name', 'result', 'time_stamp', 'score_result', 'score'])
        
        # Send the reponse table description to Qlik
        self._send_table_description("fit")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(4)
        
        # Finally send the response
        return self.response
    
    # STAGE 2 : Allow for larger datasets by using partial fitting methods avaialble with some sklearn algorithmns
    # def partial_fit(self):
        
    def predict(self, load_script=False, variant="predict"):
        """
        Return a prediction by applying an existing model to the supplied data.
        If variant='predict_proba', return the predicted probabilties for each sample. Only applicable for certain classes.
        If variant='predict_log_proba', return the log probabilities for each sample. Only applicable for certain classes.
        This method can be called from a chart expression or the load script in Qlik.
        The load_script flag needs to be set accordingly for the correct response.
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData', 'strData']
        col_headers = ['model_name', 'n_features']
        feature_col_num = 1
        
        # An additional key field column is expected if the call is made through the load script
        if load_script:
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['model_name', 'key', 'n_features']
            feature_col_num = 2
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
               
        # Initialize the persistent model
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the model from cache or disk
        self._get_model()
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(3)
        
        if load_script:
            # Set the key column as the index
            self.request_df.set_index("key", drop=False, inplace=True)
        
        # Split the features provided as a string into individual columns
        self.X = pd.DataFrame([x[feature_col_num].split("|") for x in self.request_df.values.tolist()],\
                                     columns=self.model.features_df.loc[:,"name"].tolist(),\
                                     index=self.request_df.index)
        
        # Convert the data types based on feature definitions 
        self.X = utils.convert_types(self.X, self.model.features_df)
        
        if variant == 'predict_proba' or variant == 'predict_log_proba':
            # If probabilities need to be returned
            if variant == 'predict_proba':
                # Get the predicted probability for each sample 
                self.y = self.model.pipe.predict_proba(self.X)
            elif variant == 'predict_log_proba':
                # Get the log probability for each sample
                self.y = self.model.pipe.predict_log_proba(self.X)
                
            # Prepare a list of probability by class for each sample
            probabilities = []

            for a in self.y:
                s = ""
                i = 0
                for b in a:
                    s = s + ", {0}: {1:.3f}".format(self.model.pipe.steps[self.model.estimation_step][1].classes_[i], b)
                    i = i + 1
                probabilities.append(s[2:])
            
            self.y = probabilities
                
        else:
            # Predict y for X using the previously fit pipeline
            self.y = self.model.pipe.predict(self.X)
            
        # Prepare the response
        self.response = pd.DataFrame(self.y, columns=["result"], index=self.X.index)
        
        if load_script:
            # Add the key field column to the response
            self.response = self.request_df.join(self.response).drop(['n_features'], axis=1)
        
            # If the function was called through the load script we return a Data Frame
            self._send_table_description("predict")
            
            # Debug information is printed to the terminal and logs if the paramater debug = true
            if self.model.debug:
                self._print_log(4)
            
            return self.response
            
        # If the function was called through a chart expression we return a Series
        else:
            # Debug information is printed to the terminal and logs if the paramater debug = true
            if self.model.debug:
                self._print_log(4)
            
            return self.response.loc[:,'result']
    
    
    # STAGE 3 : If feasible, allow transient models that can be setup and used from chart expressions
    # def fit_predict(self):
    
    # STAGE 2 : Provide metrics to assess prediction error beyond the score() method
    # def get_metrics():
    
    # STAGE 2: Implement feature_importances_ for applicable algorithms
    
    # STAGE 2: Allow adding dimensionality reduction to the pipeline
    
    def get_features_expression(self):
        """
        Get a string that can be evaluated in Qlik to get the features portion of the predict function
        """
        
        # Interpret the request data based on the expected row and column structure
        row_template = ['strData']
        col_headers = ['model_name']
        
        # Create a Pandas Data Frame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)
        
        # Initialize the persistent model
        self.model = PersistentModel()
        
        # Get the model name from the request dataframe
        self.model.name = self.request_df.loc[0, 'model_name']
        
        # Get the model from cache or disk
        self._get_model()
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(3)
        
        # Prepare the expression as a string
        delimiter = " &'|'& "
        features = self.model.features_df["name"].tolist()
        self.response = pd.Series(delimiter.join(["[" + f + "]" for f in features]))
        
        # Send the reponse table description to Qlik
        self._send_table_description("expression")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(4)
        
        # Finally send the response
        return self.response
    
    def _set_params(self, estimator_args, scaler_args, execution_args, dim_reduction_args=None):
        """
        Set input parameters based on the request.
        :
        :Refer to the sklearn API Reference for parameters avaialble for specific algorithms and scalers
        :http://scikit-learn.org/stable/modules/classes.html#api-reference
        :
        :Additional parameters used by this SSE are: 
        :overwrite, test_size, randon_state, compress, retain_data, debug
        :For details refer to the GitHub project: https://github.com/nabeel-qlik/qlik-py-tools
        """
        
        # Set default values which will be used if execution arguments are not passed
        
        # Execution parameters:
        self.model.overwrite = False
        self.model.debug = False
        self.model.test_size = 0.33
        self.model.random_state = 42
        self.model.compress = 3
        self.model.retain_data = False
        
        # Set execution parameters
                
        # If the execution key word arguments were included in the request, get the parameters and values
        if len(execution_args) > 0:
            
            # Transform the string of arguments into a dictionary
            execution_args = utils.get_kwargs(execution_args)
            
            # Set the overwite parameter if any existing model with the specified name should be overwritten
            if 'overwrite' in execution_args:
                self.model.overwrite = 'true' == execution_args['overwrite'].lower()
            
            # Set the test_size parameter that will be used to split the samples into training and testing data sets
            # Default value is 0.33, i.e. we use 66% of the samples for training and 33% for testing
            if 'test_size' in execution_args:
                self.model.test_size = locale.atof(execution_args['test_size'])
            
            # Seed used by the random number generator when generating the training testing split
            if 'random_state' in execution_args:
                self.model.random_state = locale.atoi(execution_args['random_state'])
            
            # Compression level between 1-9 used by joblib when saving the model
            if 'compress' in execution_args:
                self.model.compress = locale.atoi(execution_args['compress'])
                
            # Flag to determine if the training and test data should be saved in the model
            if 'retain_data' in execution_args:
                self.model.retain_data = 'true' == execution_args['retain_data'].lower()
                       
            # Set the debug option for generating execution logs
            # Valid values are: true, false
            if 'debug' in execution_args:
                self.model.debug = 'true' == execution_args['debug'].lower()
                
                # Additional information is printed to the terminal and logs if the paramater debug = true
                if self.model.debug:
                    # Increment log counter for the class. Each instance of the class generates a new log.
                    self.__class__.log_no += 1

                    # Create a log file for the instance
                    # Logs will be stored in ..\logs\SKLearn Log <n>.txt
                    self.logfile = os.path.join(os.getcwd(), 'logs', 'SKLearn Log {}.txt'.format(self.log_no))
                    
                    # Create dictionary of parameters to display for debug
                    self.exec_params = {"overwrite":self.model.overwrite, "test_size":self.model.test_size,\
                                        "random_state":self.model.random_state, "compress":self.model.compress,\
                                        "retain_data":self.model.retain_data, "debug":self.model.debug}

                    self._print_log(1)
        
        # If the scaler key word arguments were included in the request, get the parameters and values
        if len(scaler_args) > 0:
            
            # Transform the string of arguments into a dictionary
            scaler_args = utils.get_kwargs(scaler_args)
                   
            # Set scaler arguments that will be used when preprocessing the data
            # Valid values are: StandardScaler, MinMaxScaler, MaxAbsScaler, RobustScaler and QuantileTransformer
            # More information here: http://scikit-learn.org/stable/modules/preprocessing.html
            if 'scaler' in scaler_args:
                self.model.scaler = scaler_args.pop('scaler')
                
                if 'missing' in scaler_args:
                    self.model.missing = scaler_args.pop('missing').lower()
                
                if 'scale_hashed' in scaler_args:
                    self.model.scale_hashed = 'true' == scaler_args.pop('scale_hashed').lower()
                
                # Get the rest of the scaler parameters, converting values to the correct data type
                self.model.scaler_kwargs = utils.get_kwargs_by_type(scaler_args) 
            else:
                err = "Arguments for scaling did not include the scaler name e.g StandardScaler"
                self._print_exception(err, Exception(err))
            
        # If the estimator key word arguments were included in the request, get the parameters and values
        if len(estimator_args) > 0:
            
            # Transform the string of arguments into a dictionary
            estimator_args = utils.get_kwargs(estimator_args)
                   
            # Set estimator arguments that will be used when preprocessing the data
            # The parameters available will depend on the selected estimator
            # More information here: http://scikit-learn.org/stable/modules/classes.html#api-reference
            if 'estimator' in estimator_args:
                self.model.estimator = estimator_args.pop('estimator')
                
                # Get the rest of the estimator parameters, converting values to the correct data type
                self.model.estimator_kwargs = utils.get_kwargs_by_type(estimator_args)  
            else:
                err = "Arguments for estimator did not include the estimator class e.g. RandomForestClassifier"
                self._print_exception(err, Exception(err))  
        
        # If dimensionality reduction key word arguments were included in the request, get the parameters and values
        if dim_reduction_args is not None:
            # Transform the string of arguments into a dictionary
            dim_reduction_args = utils.get_kwargs(dim_reduction_args)
                   
            # Set dim_reduction arguments that will be used after preprocessing the data
            # The parameters available will depend on the selected dimensionality reduction method
            # Acceptable classes are PCA, KernelPCA, IncrementalPCA, TruncatedSVD
            # More information here: http://scikit-learn.org/stable/modules/classes.html#api-reference
            if 'reduction' in dim_reduction_args:
                self.model.reduction = dim_reduction_args.pop('reduction')
                
                # Get the rest of the dim_reduction parameters, converting values to the correct data type
                self.model.dim_reduction_args = utils.get_kwargs_by_type(dim_reduction_args)  
            else:
                err = "Arguments for dimensionality reduction did not include the class e.g. PCA"
                self._print_exception(err, Exception(err))
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(2)
              
    def _send_table_description(self, variant):
        """
        Send the table description to Qlik as meta data.
        Only used when the SSE is called from the Qlik load script.
        """
        
        # Set up the table description to send as metadata to Qlik
        self.table = SSE.TableDescription()
        self.table.name = "SSE-Response"
        self.table.numberOfRows = len(self.response)

        # Set up fields for the table
        if variant == "setup":
            self.table.fields.add(name="model_name")
            self.table.fields.add(name="result")
            self.table.fields.add(name="timestamp")
        elif variant == "features":
            self.table.fields.add(name="model_name")
            self.table.fields.add(name="sort_order", dataType=1)
            self.table.fields.add(name="feature")
            self.table.fields.add(name="var_type")
            self.table.fields.add(name="data_type")
            self.table.fields.add(name="strategy")
            self.table.fields.add(name="hash_length", dataType=1)
        elif variant == "fit":
            self.table.fields.add(name="model_name")
            self.table.fields.add(name="result")
            self.table.fields.add(name="time_stamp")
            self.table.fields.add(name="score_result")
            self.table.fields.add(name="score", dataType=1)
        elif variant == "predict":
            self.table.fields.add(name="model_name")
            self.table.fields.add(name="key")
            self.table.fields.add(name="prediction")
        elif variant == "expression":
            self.table.fields.add(name="result")
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(5)
            
        # Send table description
        table_header = (('qlik-tabledescription-bin', self.table.SerializeToString()),)
        self.context.send_initial_metadata(table_header)
    
    def _get_model(self):
        """
        Get the model from the class model cache or disk.
        Update the cache if loading from disk.
        Return the model.
        """
        
        if self.model.name in self.__class__.model_cache:
            # Load the model from cache
            self.model = self.__class__.model_cache[self.model.name]
            
            # Debug information is printed to the terminal and logs if the paramater debug = true
            if self.model.debug:
                self._print_log(6)
        else:
            # Load the model from disk
            self.model = self.model.load(self.model.name, self.path)
            
            # Debug information is printed to the terminal and logs if the paramater debug = true
            if self.model.debug:
                self._print_log(7)
            
            # Update the cache to keep this model in memory
            self._update_cache()
    
    def _update_cache(self):
        """
        Maintain a cache of recently used models at the class level
        """
        
        # Check if the model cache is full
        if self.__class__.cache_limit == len(self.__class__.model_cache):
            # Remove the oldest item from the cache if exceeding cache limit
            self.__class__.model_cache.popitem(last=False)
        
        # Remove the obsolete version of the model from the cache
        if self.model.name in self.__class__.model_cache:
            del self.__class__.model_cache[self.model.name]
        
        # Add the current model to the cache
        self.__class__.model_cache[self.model.name] = self.model
        
        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.model.debug:
            self._print_log(8)
    
    def _print_log(self, step):
        """
        Output useful information to stdout and the log file if debugging is required.
        :step: Print the corresponding step in the log
        """
        
        if self.logfile is None:
            # Increment log counter for the class. Each instance of the class generates a new log.
            self.__class__.log_no += 1

            # Create a log file for the instance
            # Logs will be stored in ..\logs\SKLearn Log <n>.txt
            self.logfile = os.path.join(os.getcwd(), 'logs', 'SKLearn Log {}.txt'.format(self.log_no))
        
        if step == 1:
            # Output log header
            sys.stdout.write("\nSKLearnForQlik Log: {0} \n\n".format(time.ctime(time.time())))
            
            with open(self.logfile,'w') as f:
                f.write("SKLearnForQlik Log: {0} \n\n".format(time.ctime(time.time())))
                
        elif step == 2:
            # Output the parameters
            sys.stdout.write("Model Name: {0}\n\n".format(self.model.name))
            sys.stdout.write("Execution arguments: {0}\n\n".format(self.exec_params))
            sys.stdout.write("Scaler: {0}, missing: {1}, scale_hashed: {2}\n".format(\
                                                                                     self.model.scaler, self.model.missing,\
                                                                                     self.model.scale_hashed))
            sys.stdout.write("Scaler kwargs: {0}\n\n".format(self.model.scaler_kwargs))
            if self.model.dim_reduction:
                sys.stdout.write("Reduction: {0}\nReduction kwargs: {1}\n\n".format(self.model.reduction,\
                                                                                    self.model.dim_reduction_kwargs))
            sys.stdout.write("Estimator: {0}\nEstimator kwargs: {1}\n\n".format(self.model.estimator,\
                                                                                self.model.estimator_kwargs))
            
            with open(self.logfile,'a') as f:
                f.write("Model Name: {0}\n\n".format(self.model.name))
                f.write("Execution arguments: {0}\n\n".format(self.exec_params))
                f.write("Scaler: {0}, missing: {1}, scale_hashed: {2}\n".format(self.model.scaler, self.model.missing,\
                                                                                self.model.scale_hashed))
                f.write("Scaler kwargs: {0}\n\n".format(self.model.scaler_kwargs))
                if self.model.dim_reduction:
                    f.write("Reduction: {0}\nReduction kwargs: {1}\n\n".format(self.model.reduction,\
                                                                               self.model.dim_reduction_kwargs))
                f.write("Estimator: {0}\nEstimator kwargs: {1}\n\n".format(self.model.estimator,self.model.estimator_kwargs))
                
        elif step == 3:                    
            # Output the request dataframe
            sys.stdout.write("REQUEST: {0} rows x cols\n\n".format(self.request_df.shape))
            sys.stdout.write("{0} \n\n".format(self.request_df.to_string()))
            
            with open(self.logfile,'a') as f:
                f.write("REQUEST: {0} rows x cols\n\n".format(self.request_df.shape))
                f.write("{0} \n\n".format(self.request_df.to_string()))
        
        elif step == 4:
            # Output the response dataframe/series
            sys.stdout.write("RESPONSE: {0} rows x cols\n\n".format(self.response.shape))
            sys.stdout.write("{0} \n\n".format(self.response.to_string()))
            
            with open(self.logfile,'a') as f:
                f.write("RESPONSE: {0} rows x cols\n\n".format(self.response.shape))
                f.write("{0} \n\n".format(self.response.to_string()))
                 
        elif step == 5:
            # Print the table description if the call was made from the load script
            sys.stdout.write("\nTABLE DESCRIPTION SENT TO QLIK:\n\n{0} \n\n".format(self.table))
            
            # Write the table description to the log file
            with open(self.logfile,'a') as f:
                f.write("\nTABLE DESCRIPTION SENT TO QLIK:\n\n{0} \n\n".format(self.table))
        
        elif step == 6:
            # Message when model is loaded from cache
            sys.stdout.write("\nModel {0} loaded from cache.\n\n".format(self.model.name))
            
            with open(self.logfile,'a') as f:
                f.write("\nModel {0} loaded from cache.\n\n".format(self.model.name))
            
        elif step == 7:
            # Message when model is loaded from disk
            sys.stdout.write("\nModel {0} loaded from disk.\n\n".format(self.model.name))
            
            with open(self.logfile,'a') as f:
                f.write("\nModel {0} loaded from disk.\n\n".format(self.model.name))
            
        elif step == 8:
            # Message when cache is updated
            sys.stdout.write("\nCache updated. Models in cache:\n{0}\n\n".format\
                             ([k for k,v in self.__class__.model_cache.items()]))
            
            with open(self.logfile,'a') as f:
                f.write("\nCache updated. Models in cache:\n{0}\n\n".format([k for k,v in self.__class__.model_cache.items()]))
    
    def _print_exception(self, s, e):
        """
        Output exception message to stdout and also to the log file if debugging is required.
        :s: A description for the error
        :e: The exception
        """
        
        # Output exception message
        sys.stdout.write("\n{0}: {1} \n\n".format(s, e))
        
        if self.debug:
            with open(self.logfile,'a') as f:
                f.write("\n{0}: {1} \n\n".format(s, e))