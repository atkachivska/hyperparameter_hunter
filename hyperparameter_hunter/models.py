##################################################
# Import Own Assets
##################################################
from hyperparameter_hunter.settings import G
from hyperparameter_hunter.utils.general_utils import type_val
from hyperparameter_hunter.utils.metrics_utils import wrap_xgboost_metric

##################################################
# Import Miscellaneous Assets
##################################################
from contextlib import suppress
import inspect
import sys
from types import MethodType
import warnings

##################################################
# Import Learning Assets
##################################################
import sklearn.utils as sklearn_utils

warnings.filterwarnings('ignore')
load_model = lambda _: _


def model_selector(model_initializer):
    """Selects the appropriate Model class to use for `model_initializer`

    Parameters
    ----------
    model_initializer: callable
        The callable used to create an instance of some algorithm

    Returns
    -------
    :class:`Model`, or one of its children"""
    try:
        if model_initializer.__name__ in ('KerasClassifier', 'KerasRegressor'):
            return KerasModel
        elif model_initializer.__name__ in ('XGBClassifier', 'XGBRegressor'):
            return XGBoostModel
        else:
            return Model
    except AttributeError:
        return Model


class Model(object):
    def __init__(
            self, model_initializer, initialization_params, extra_params, train_input=None, train_target=None,
            validation_input=None, validation_target=None, do_predict_proba=False, target_metric=None, metrics_map=None,
    ):
        """Handles initialization, fitting, and prediction for provided algorithms. Consider documentation for children of
        :class:`Model` to be identical to that of :class:`Model`, except where noted

        Parameters
        ----------
        model_initializer: Class
            Expected to implement at least the following methods: 1) `__init__`, to which :attr:`initialization_params` will
            usually be provided unless stated otherwise in a child class's documentation - like :class:`KerasModel`. 2) `fit`, to
            which :attr:`train_input`, and :attr:`train_target` will be provided, in addition to the contents of
            :attr:`extra_params['fit']` in some child classes - like :class:`XGBoostModel`. 3) `predict`, or `predict_proba` if
            applicable, which should accept any array-like input of shape: (<num_samples>, `train_input.shape[1]`)
        initialization_params: Dict
            A dict containing all arguments accepted by :meth:`__init__` of the class :attr:`model_initializer`, unless stated
            otherwise in a child class's documentation - like :class:`KerasModel`. Arguments pertaining to random seeds will be
            ignored
        extra_params: Dict, default={}
            A dict of special parameters that are passed to a model's non-initialization methods in special cases (such as `fit`,
            `predict`, `predict_proba`, and `score`). `extra_params` are not used for all models. See the documentation for the
            appropriate descendant of :class:`models.Model` for information about how it handles `extra_params`
        train_input: `pandas.DataFrame`
            The model's training input data
        train_target: `pandas.DataFrame`
            The true labels corresponding to the rows of :attr:`train_input`
        validation_input: `pandas.DataFrame`, or None
            The model's validation input data to evaluate performance during fitting
        validation_target: `pandas.DataFrame`, or None
            The true labels corresponding to the rows of :attr:`validation_input`
        do_predict_proba: Boolean, default=False
            If True, :meth:`models.Model.fit` will call :meth:`models.Model.model.predict_proba`. Else, it will
            call :meth:`models.Model.model.predict`
        target_metric: Tuple
            Used by some child classes (like :class:`XGBoostModel`) to provide validation data to :meth:`model.fit`
        metrics_map: Dict
            Used by some child classes (like :class:`XGBoostModel`) to provide validation data to :meth:`model.fit`"""
        self.model_initializer = model_initializer
        self.initialization_params = initialization_params
        self.extra_params = extra_params or {}

        self.train_input = train_input
        self.train_target = train_target
        self.validation_input = validation_input
        self.validation_target = validation_target
        self.do_predict_proba = do_predict_proba
        self.target_metric = target_metric
        self.metrics_map = metrics_map

        self.model = None
        self.epochs_elapsed = None

        self.initialize_model()

    def initialize_model(self):
        """Create an instance of a model using :attr:`model_initializer`, with :attr:`initialization_params` as input"""
        #################### Model Class that can be Initialized with model_params ####################
        try:
            self.model = self.model_initializer(**self.initialization_params)
        except Exception as _ex:
            raise type(_ex)(
                str(_ex) + '\nReceived invalid model_initializer of type {}: {}'.format(*type_val(self.model_initializer))
            ).with_traceback(sys.exc_info()[2])

    def fit(self):
        """Train a model according to :attr:`extra_params['fit']` (if appropriate) on training data"""
        expected_fit_parameters = list(inspect.signature(self.model.fit).parameters)
        fit_kwargs = {}
        if 'verbose' in expected_fit_parameters:
            fit_kwargs['verbose'] = False
        if 'silent' in expected_fit_parameters:
            fit_kwargs['silent'] = True

        fit_kwargs = dict(
            fit_kwargs, **{_k: _v for _k, _v in self.extra_params.get('fit', {}).items() if _k not in ['X', 'y', 'eval_set']}
        )

        try:
            self.model = self.model.fit(self.train_input, self.train_target, **fit_kwargs)
        except (TypeError, sklearn_utils.DataConversionWarning):
            try:
                self.model = self.model.fit(self.train_input.values, self.train_target.values[:, 0], **fit_kwargs)
            except Exception as _ex:
                raise _ex

    def predict(self, input_data):
        """Generate model predictions for `input_data`

        Parameters
        ----------
        input_data: Array-like
            Data containing the same number of features as were trained on, for which the model will predict output values"""
        if input_data is None:
            return None

        try:
            if self.do_predict_proba is True:
                prediction = self.model.predict_proba(input_data)
            else:
                prediction = self.model.predict(input_data)
        except Exception as _ex:
            raise _ex

        with suppress(IndexError):
            prediction = prediction[:, 0]

        return prediction


class XGBoostModel(Model):
    def __init__(
            self, model_initializer, initialization_params, extra_params, train_input=None, train_target=None,
            validation_input=None, validation_target=None, do_predict_proba=False, target_metric=None, metrics_map=None,
    ):
        """A special Model class for handling XGBoost algorithms. Consider documentation to be identical to that of
        :class:`Model`, except where noted

        Parameters
        ----------
        model_initializer: :class:`xgboost.sklearn.XGBClassifier`, or :class:`xgboost.sklearn.XGBRegressor`
            See :class:`Model`
        initialization_params: See :class:`Model`
        extra_params: Dict, default={}
            Useful keys: ['fit', 'predict']. If 'fit' is a key with a dict value, its contents will be provided to
            :meth:`xgboost.sklearn.XGBModel.fit`, with the exception of the following: ['X', 'y', 'eval_set']. If any of the
            aforementioned keys are in :attr:`extra_params['fit']` or if :attr:`extra_params['fit']` is provided, but is not a
            dict, an Exception will be raised.
            Unless it is explicitly given, the 'eval_metric' argument to :meth:`xgboost.sklearn.XGBModel.fit` will be
            automatically determined by the metric string in :attr:`target_metric`, the wrapping for XGBoost of which will be
            performed automatically.
            The 'eval_set' argument to :meth:`xgboost.sklearn.XGBModel.fit` will be: [(`train_input`, `train_target`),
            (`validation_input`, `validation_target`)]. If validation data is None, it will be excluded.
        train_input: See :class:`Model`
        train_target: See :class:`Model`
        validation_input: See :class:`Model`
        validation_target: See :class:`Model`
        do_predict_proba: See :class:`Model`
        target_metric: Tuple
            Used to determine the 'eval_metric' argument to :meth:`xgboost.sklearn.XGBModel.fit`. See the documentation for
            :attr:`XGBoostModel.extra_params` for more information
        metrics_map: See :class:`Model`"""
        if model_initializer.__name__ not in ('XGBClassifier', 'XGBRegressor'):
            raise ValueError('XGBoostModel given invalid model_initializer: {} - {}\nTry using the standard Model class'.format(
                type(model_initializer), (model_initializer.__name__ or model_initializer)
            ))

        super().__init__(
            model_initializer, initialization_params, extra_params, train_input=train_input, train_target=train_target,
            validation_input=validation_input, validation_target=validation_target, do_predict_proba=do_predict_proba,
            target_metric=target_metric, metrics_map=metrics_map,
        )

    # FLAG: ORIGINAL BELOW
    # TODO: Shouldn't be default behavior to include `eval_set` below - Results in unexpectedly long execution times - Rework
    # def fit(self):
    #     #################### Build eval_set ####################
    #     eval_set = [(self.train_input, self.train_target)]
    #     if (self.validation_input is not None) and (self.validation_target is not None):
    #         eval_set.append((self.validation_input, self.validation_target))
    #
    #     #################### Combine Fit Parameters ####################
    #     fit_kwargs = dict(dict(
    #         eval_set=eval_set,
    #         verbose=False,  # Default to verbose=False (in contradiction with XGBoost docs) if not explicitly given
    #     ), **{_k: _v for _k, _v in self.extra_params.get('fit', {}).items() if _k not in ['X', 'y', 'eval_set']})
    #
    #     #################### Build eval_metric ####################
    #     if 'eval_metric' not in fit_kwargs:
    #         target_metric_name = self.target_metric[-1]
    #         fit_kwargs['eval_metric'] = wrap_xgboost_metric(self.metrics_map[target_metric_name], target_metric_name)
    #         # eval_metric scores may be higher than reported scores depending on predict/predict_proba
    #
    #     self.model.fit(self.train_input, self.train_target, **fit_kwargs)
    # FLAG: ORIGINAL ABOVE


class KerasModel(Model):
    def __init__(
            self, model_initializer, initialization_params, extra_params, train_input=None, train_target=None,
            validation_input=None, validation_target=None, do_predict_proba=False, target_metric=None, metrics_map=None,
    ):
        """A special Model class for handling Keras neural networks. Consider documentation to be identical to that of
        :class:`Model`, except where noted

        Parameters
        ----------
        model_initializer: :class:`keras.wrappers.scikit_learn.KerasClassifier`, or `keras.wrappers.scikit_learn.KerasRegressor`
            Expected to implement at least the following methods: 1) `__init__`, to which :attr:`initialization_params` will
            usually be provided unless stated otherwise in a child class's documentation - like :class:`KerasModel`. 2) `fit`, to
            which :attr:`train_input`, and :attr:`train_target` will be provided, in addition to the contents of
            :attr:`extra_params['fit']` in some child classes - like :class:`XGBoostModel`. 3) `predict`, or `predict_proba` if
            applicable, which should accept any array-like input of shape: (<num_samples>, `train_input.shape[1]`)
        initialization_params: Dict containing `build_fn`
            A dictionary containing the single key: `build_fn`, which is a callable function that returns a compiled Keras model
        extra_params: Dict, default={}
            The parameters expected to be passed to the extra methods of the compiled Keras model. Such methods include (but are
            not limited to) `fit`, `predict`, and `predict_proba`. Some of the common parameters given here include `epochs`,
            `batch_size`, and `callbacks`
        train_input: `pandas.DataFrame`
            The model's training input data
        train_target: `pandas.DataFrame`
            The true labels corresponding to the rows of :attr:`train_input`
        validation_input: `pandas.DataFrame`, or None
            The model's validation input data to evaluate performance during fitting
        validation_target: `pandas.DataFrame`, or None
            The true labels corresponding to the rows of :attr:`validation_input`
        do_predict_proba: Boolean, default=False
            If True, :meth:`Model.fit` will call :meth:`models.Model.model.predict_proba`. Else, it will
            call :meth:`models.Model.model.predict`
        target_metric: Tuple
            Used by some child classes (like :class:`XGBoostModel`) to provide validation data to :meth:`model.fit`
        metrics_map: Dict
            Used by some child classes (like :class:`XGBoostModel`) to provide validation data to :meth:`model.fit`"""
        if model_initializer.__name__ not in ('KerasClassifier', 'KerasRegressor'):
            raise ValueError('KerasModel given invalid model_initializer: {} - {}\nTry using the standard Model class'.format(
                type(model_initializer), (model_initializer.__name__ or model_initializer)
            ))

        super().__init__(
            model_initializer, initialization_params, extra_params, train_input=train_input, train_target=train_target,
            validation_input=validation_input, validation_target=validation_target, do_predict_proba=do_predict_proba,
            target_metric=target_metric, metrics_map=metrics_map,
        )

        global load_model
        from keras.models import load_model

    def initialize_model(self):
        """Create an instance of a model using :attr:`model_initializer`, with :attr:`initialization_params` as input"""
        self.validate_keras_params()
        self.model = self.initialize_keras_neural_network()

    def fit(self):
        """Train a model according to :attr:`extra_params['fit']` (if appropriate) on training data"""
        try:
            self.model.fit(self.train_input, self.train_target)
        except Exception as _ex:
            G.warn(F'KerasModel.fit() failed with Exception: {_ex}\nAttempting standard fit method')
            super().fit()
        finally:
            #################### Record Epochs Elapsed if Model has 'epoch' Attribute ####################
            with suppress(AttributeError):
                self.epochs_elapsed = len(self.model.epoch)

            #################### Load Model Checkpoint if Possible ####################
            for callback in self.extra_params.get('callbacks', []):
                if callback.__class__.__name__ == 'ModelCheckpoint':
                    self.model.model.load_weights(callback.filepath)

    def get_input_shape(self, get_dim=False):
        """Calculate the shape of the input that should be expected by the model

        Parameters
        ----------
        get_dim: Boolean, default=False
            If True, instead of returning an input_shape tuple, an input_dim scalar will be returned

        Returns
        -------
        Tuple, or scalar
            If get_dim=False, an input_shape tuple. Else, an input_dim scalar"""
        if self.train_input is not None:
            if get_dim:
                return self.train_input.shape[1]
            return self.train_input.shape[1:]
        elif self.validation_input is not None:
            if get_dim:
                return self.validation_input.shape[1]
            return self.validation_input.shape[1:]
        else:
            raise ValueError('To initialize a KerasModel, train_input data, or input_dim must be provided')

    def validate_keras_params(self):
        """Ensure provided input parameters are properly formatted"""
        #################### Check Keras Import Hooks ####################
        necessary_import_hooks = ['keras_layer']
        for hook in necessary_import_hooks:
            if hook not in G.import_hooks:
                raise ImportError(F'The following import hook must be established before Keras is imported: {hook!r}')

        #################### build_fn ####################
        if not isinstance(self.initialization_params, dict):
            raise TypeError(F'initialization_params must be a dict containing "build_fn".\nReceived:{self.initialization_params}')
        if 'build_fn' not in self.initialization_params.keys():
            raise KeyError(F'initialization_params must contain the "build_fn" key.\nReceived: {self.initialization_params}')

        bad_extra_keys = {'build_fn', 'input_shape', 'input_dim', 'validation_data', 'validation_split', 'x', 'y'}
        bad_keys_found = bad_extra_keys.intersection(self.extra_params)
        if len(bad_keys_found) > 0:
            raise KeyError(F'extra_params may not contain the following keys: {bad_extra_keys}.\nFound: {bad_keys_found}')

    def initialize_keras_neural_network(self):
        """Initialize Keras model wrapper (:attr:`model_initializer`) with :attr:`initialization_params`, :attr:`extra_params`,
        and validation_data if it can be found, as well as the input dimensions for the model"""
        validation_data = None
        if (self.validation_input is not None) and (self.validation_target is not None):
            validation_data = (self.validation_input, self.validation_target)

        return self.model_initializer(
            build_fn=self.initialization_params['build_fn'],
            input_shape=self.get_input_shape(),
            validation_data=validation_data,
            **self.extra_params,
        )


if __name__ == '__main__':
    pass
