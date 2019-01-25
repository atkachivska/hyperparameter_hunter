##################################################
# Import Own Assets
##################################################
from hyperparameter_hunter.library_helpers.keras_helper import parameterize_compiled_keras_model

##################################################
# Import Miscellaneous Assets
##################################################
from pkg_resources import get_distribution
import pytest

try:
    keras = pytest.importorskip("keras")
except Exception:
    raise

##################################################
# Import Learning Assets
##################################################
from keras.optimizers import Adam, RMSprop
from keras.layers import Dense, Dropout, Embedding, Flatten, SpatialDropout1D
from keras.losses import binary_crossentropy, mean_absolute_error
from keras.models import Sequential

##################################################
# Parametrization Helper Dicts
##################################################
default_dense = {
    "activation": None,
    "use_bias": True,
    "kernel_initializer": "glorot_uniform",
    "bias_initializer": "zeros",
    "kernel_regularizer": None,
    "bias_regularizer": None,
    "activity_regularizer": None,
    "kernel_constraint": None,
    "bias_constraint": None,
}
default_dropout = {"noise_shape": None, "seed": None}


##################################################
# Dummy Model #0
##################################################
def dummy_0_build_fn(input_shape=(30,)):
    model = Sequential(
        [
            Dense(50, kernel_initializer="uniform", input_shape=input_shape, activation="relu"),
            Dropout(0.5),
            Dense(1, kernel_initializer="uniform", activation="sigmoid"),
        ]
    )
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model


dummy_0_layers = [
    {
        "class_name": "Dense",
        "__hh_default_args": ["units"],
        "__hh_default_kwargs": default_dense,
        "__hh_used_args": (50,),
        "__hh_used_kwargs": dict(
            kernel_initializer="uniform", input_shape=(30,), activation="relu"
        ),
    },
    {
        "class_name": "Dropout",
        "__hh_default_args": ["rate"],
        "__hh_default_kwargs": default_dropout,
        "__hh_used_args": (0.5,),
        "__hh_used_kwargs": {},
    },
    {
        "class_name": "Dense",
        "__hh_default_args": ["units"],
        "__hh_default_kwargs": default_dense,
        "__hh_used_args": (1,),
        "__hh_used_kwargs": dict(kernel_initializer="uniform", activation="sigmoid"),
    },
]
dummy_0_compile_params = {
    "optimizer": "adam",
    "optimizer_params": Adam().get_config(),
    "metrics": ["accuracy"],
    "metrics_names": ["loss", "acc"],
    "loss_functions": [binary_crossentropy],
    "loss_function_names": ["binary_crossentropy"],
    "loss_weights": None,
    "sample_weight_mode": None,
    "weighted_metrics": None,
    "target_tensors": None,
    "compile_kwargs": {},
}


##################################################
# Dummy Model #1
##################################################
# noinspection PyUnusedLocal
def dummy_1_build_fn(input_shape=(1,)):
    model = Sequential(
        [
            Embedding(input_dim=9999, output_dim=200, input_length=100, trainable=True),
            SpatialDropout1D(rate=0.5),
            Flatten(),
            Dense(100, activation="relu"),
            Dense(1, activation="sigmoid"),
        ]
    )
    model.compile(
        optimizer=RMSprop(lr=0.02, decay=0.001),
        loss=mean_absolute_error,
        metrics=["mean_absolute_error"],
    )
    return model


dummy_1_layers = [
    {
        "class_name": "Embedding",
        "__hh_default_args": ["input_dim", "output_dim"],
        "__hh_default_kwargs": dict(
            embeddings_initializer="uniform",
            embeddings_regularizer=None,
            activity_regularizer=None,
            embeddings_constraint=None,
            mask_zero=False,
            input_length=None,
        ),
        "__hh_used_args": tuple(),
        "__hh_used_kwargs": dict(input_dim=9999, output_dim=200, input_length=100, trainable=True),
    },
    {
        "class_name": "SpatialDropout1D",
        "__hh_default_args": ["rate"],
        "__hh_default_kwargs": dict(),
        "__hh_used_args": tuple(),
        "__hh_used_kwargs": dict(rate=0.5),
    },
    {
        "class_name": "Flatten",
        "__hh_default_args": [],
        "__hh_default_kwargs": (
            dict(data_format=None) if get_distribution("keras").version >= "2.2.0" else {}
        ),
        "__hh_used_args": tuple(),
        "__hh_used_kwargs": dict(),
    },
    {
        "class_name": "Dense",
        "__hh_default_args": ["units"],
        "__hh_default_kwargs": default_dense,
        "__hh_used_args": (100,),
        "__hh_used_kwargs": dict(activation="relu"),
    },
    {
        "class_name": "Dense",
        "__hh_default_args": ["units"],
        "__hh_default_kwargs": default_dense,
        "__hh_used_args": (1,),
        "__hh_used_kwargs": dict(activation="sigmoid"),
    },
]
dummy_1_compile_params = {
    "optimizer": "rmsprop",
    "optimizer_params": dict(
        RMSprop().get_config(), **dict(lr=pytest.approx(0.02), decay=pytest.approx(0.001))
    ),
    "metrics": ["mean_absolute_error"],
    "metrics_names": ["loss", "mean_absolute_error"],
    "loss_functions": [mean_absolute_error],
    "loss_function_names": ["mean_absolute_error"],
    "loss_weights": None,
    "sample_weight_mode": None,
    "weighted_metrics": None,
    "target_tensors": None,
    "compile_kwargs": {},
}


##################################################
# `parameterize_compiled_keras_model` Scenarios
##################################################
@pytest.mark.parametrize(
    ["model", "layers", "compile_params"],
    [
        (dummy_0_build_fn, dummy_0_layers, dummy_0_compile_params),
        (dummy_1_build_fn, dummy_1_layers, dummy_1_compile_params),
    ],
    ids=["dummy_model_0", "dummy_model_1"],
)
def test_parameterize_compiled_keras_model(model, layers, compile_params):
    if get_distribution("keras").version < "2.2.0":
        layers.insert(
            0,
            {
                "class_name": "InputLayer",
                "__hh_default_args": None,
                "__hh_default_kwargs": None,
                "__hh_used_args": None,
                "__hh_used_kwargs": None,
            },
        )
    assert parameterize_compiled_keras_model(model()) == (layers, compile_params)
