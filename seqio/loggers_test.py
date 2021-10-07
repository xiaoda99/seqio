# Copyright 2021 The SeqIO Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for seqio.loggers."""
# pylint:disable=g-bare-generic,g-long-lambda

import json
import os

import numpy as np
from seqio import loggers
from seqio import metrics as metrics_lib
import tensorflow.compat.v2 as tf
import tensorflow_datasets as tfds

# For faster testing.
tf.compat.v1.enable_eager_execution()


class TensorBoardLoggerTest(tf.test.TestCase):

  def setUp(self):
    super().setUp()
    self.logger = loggers.TensorBoardLogger(self.create_tempdir().full_path)

  def test_logging(self):
    task_metrics = {
        "rouge1": metrics_lib.Scalar(50),
        "rouge2": metrics_lib.Scalar(100)
    }
    self.logger(
        task_name="log_eval_task", step=1, metrics=task_metrics,
        dataset=tf.data.Dataset.range(0), inferences={}, targets=[])
    task_output_dir = os.path.join(self.logger.output_dir, "log_eval_task")
    event_file = os.path.join(
        task_output_dir, tf.io.gfile.listdir(task_output_dir)[0])
    # First event is boilerplate
    serialized_events = list(tfds.as_numpy(
        tf.data.TFRecordDataset(event_file)))[1:]
    event1 = tf.compat.v1.Event.FromString(
        serialized_events[0]).summary.value[0]
    rouge1 = event1.simple_value
    tag_rouge1 = event1.tag
    event2 = tf.compat.v1.Event.FromString(
        serialized_events[1]).summary.value[0]
    rouge2 = event2.simple_value
    tag_rouge2 = event2.tag

    self.assertEqual(tag_rouge1, "eval/rouge1")
    self.assertEqual(tag_rouge2, "eval/rouge2")
    self.assertAlmostEqual(rouge1, 50, places=4)
    self.assertAlmostEqual(rouge2, 100, places=4)


class JSONLoggerTest(tf.test.TestCase):

  def _get_task_dataset_for_write_to_file_tests(self):
    x = [{"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
         {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"}]
    output_types = {
        "inputs_pretokenized": tf.string,
        "targets_pretokenized": tf.string
    }
    output_shapes = {"targets_pretokenized": [], "inputs_pretokenized": []}
    task_dataset = tf.data.Dataset.from_generator(
        lambda: x, output_types=output_types, output_shapes=output_shapes)
    return task_dataset

  def test_logging(self):
    inferences = {"predictions": ["pred0", "pred1"], "scores": [0.2, 0.3]}
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": "pred0",
        "target": "target0",
        "score": 0.2
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "prediction": "pred1",
        "target": "target1",
        "score": 0.3
    }]
    self.assertEqual(actual, expected)

  def test_n_prediction_and_scores(self):
    inferences = {"predictions": ["pred0", "pred1"], "scores": [0.2, 0.3]}
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir, write_n_results=1)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": "pred0",
        "target": "target0",
        "score": 0.2
    }]
    self.assertEqual(actual, expected)

  def test_predicitions_only(self):
    inferences = {"predictions": ["pred0", "pred1"]}
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": "pred0",
        "target": "target0",
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "prediction": "pred1",
        "target": "target1",
    }]
    self.assertEqual(actual, expected)

  def test_numpy_data(self):
    inferences = {
        "predictions": [np.zeros((2, 2)), np.ones((2, 2))],
        "scores": [0.2, 0.3]
    }
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(np.float32(100))},
           dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": [[0.0, 0.0], [0.0, 0.0]],
        "score": 0.2,
        "target": "target0",
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "prediction": [[1.0, 1.0], [1.0, 1.0]],
        "score": 0.3,
        "target": "target1",
    }]
    self.assertEqual(actual, expected)

  def test_non_serializable_prediction(self):
    inferences = {
        "predictions": [object(), object()],
        "scores": [0.2, 0.3]
    }
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "score": 0.2,
        "target": "target0",
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "score": 0.3,
        "target": "target1",
    }]
    self.assertEqual(actual, expected)

  def test_non_serializable_target(self):
    inferences = {
        "predictions": ["pred0", "pred1"],
        "scores": [0.2, 0.3]
    }
    targets = [object(), object()]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": "pred0",
        "score": 0.2,
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "prediction": "pred1",
        "score": 0.3,
    }]
    self.assertEqual(actual, expected)

  def test_prediction_bytes(self):
    inferences = {
        "predictions": [b"\x99", b"\x88"],
    }
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path
    task_dataset = self._get_task_dataset_for_write_to_file_tests()

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs_pretokenized": "i0", "targets_pretokenized": "t0"},
        "prediction": "mQ==",
        "target": "target0",
    }, {
        "input": {"inputs_pretokenized": "i1", "targets_pretokenized": "t1"},
        "prediction": "iA==",
        "target": "target1",
    }]
    self.assertEqual(actual, expected)

  def test_2d_ragged_input(self):
    x = [{"inputs": tf.ragged.constant([[9, 4, 1], [8, 1]]),
          "inputs_pretokenized": ["i0_0", "i0_1"]},
         {"inputs": tf.ragged.constant([[9, 1], [7, 2, 3, 1]]),
          "inputs_pretokenized": ["i1_0", "i1_1"]}]
    task_dataset = tf.data.Dataset.from_generator(
        lambda: x,
        output_signature={
            "inputs": tf.RaggedTensorSpec(shape=[None, None], dtype=tf.int32),
            "inputs_pretokenized": tf.TensorSpec(shape=[None], dtype=tf.string)}
    )
    inferences = {"predictions": ["pred0", "pred1"], "scores": [0.2, 0.3]}
    targets = ["target0", "target1"]
    tmp_dir = self.create_tempdir().full_path

    logger = loggers.JSONLogger(tmp_dir)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)}, dataset=task_dataset,
           inferences=inferences, targets=targets)

    # Validate the metrics file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f), {"step": 42, "accuracy": 100.0})

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-000042.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [{
        "input": {"inputs": [[9, 4, 1], [8, 1]],
                  "inputs_pretokenized": ["i0_0", "i0_1"]},
        "prediction": "pred0",
        "target": "target0",
        "score": 0.2
    }, {
        "input": {"inputs": [[9, 1], [7, 2, 3, 1]],
                  "inputs_pretokenized": ["i1_0", "i1_1"]},
        "prediction": "pred1",
        "target": "target1",
        "score": 0.3
    }]
    self.assertEqual(actual, expected)

  def test_metrics_multiple_steps(self):
    tmp_dir = self.create_tempdir().full_path

    logger = loggers.JSONLogger(tmp_dir, write_n_results=0)
    logger(task_name="test", step=42,
           metrics={"accuracy": metrics_lib.Scalar(100)},
           dataset=tf.data.Dataset.range(0), inferences={}, targets=[])

    logger(task_name="test", step=48,
           metrics={"accuracy": metrics_lib.Scalar(50)},
           dataset=tf.data.Dataset.range(0), inferences={}, targets=[])

    # Read the written jsonl file.
    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      actual = [json.loads(line.strip()) for line in f]

    expected = [
        {"step": 42, "accuracy": 100},
        {"step": 48, "accuracy": 50}]

    self.assertEqual(actual, expected)

  def test_metrics_non_serializable(self):
    tmp_dir = self.create_tempdir().full_path

    logger = loggers.JSONLogger(tmp_dir, write_n_results=0)
    logger(task_name="test", step=42,
           metrics={
               "scalar": metrics_lib.Scalar(100),
               "text": metrics_lib.Text("foo"),
               "image": metrics_lib.Image(np.ones(10)),
           },
           dataset=tf.data.Dataset.range(0), inferences={}, targets=[])

    with open(os.path.join(tmp_dir, "test-metrics.jsonl")) as f:
      self.assertDictEqual(json.load(f),
                           {"step": 42, "scalar": 100.0, "text": "foo"})

if __name__ == "__main__":
  tf.test.main()