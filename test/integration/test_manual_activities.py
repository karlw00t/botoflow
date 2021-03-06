# -*- mode:python ; fill-column:120 -*-
import time
import unittest
import os
from threading import Thread

from botoflow import (WorkflowDefinition, execute, return_,
                      ThreadedActivityExecutor, WorkflowWorker, ActivityWorker,
                      workflow_starter)

from botoflow.manual_activity_completion_client import ManualActivityCompletionClient
from utils import SWFMixIn
from various_activities import BunchOfActivities, ManualActivities


class TestManualActivities(SWFMixIn, unittest.TestCase):

    def test_one_manual_activity(self):
        swf_client = self.client
        class OneManualActivityWorkflow(WorkflowDefinition):
            def __init__(self, workflow_execution):
                super(OneManualActivityWorkflow, self).__init__(workflow_execution)

            @execute(version='1.1', execution_start_to_close_timeout=60)
            def execute(self, template):
                result = yield ManualActivities.perform_task(template=template)
                return_(result)

        wf_worker = WorkflowWorker(
            self.session, self.region, self.domain, self.task_list, OneManualActivityWorkflow)

        act_executor = ThreadedActivityExecutor(ActivityWorker(
            self.session, self.region, self.domain, self.task_list, ManualActivities()))

        with workflow_starter(self.session, self.region, self.domain, self.task_list):
            instance = OneManualActivityWorkflow.execute(template='instructions.tmpl')
            self.workflow_execution = instance.workflow_execution

        def complete_this_activity():
            activities_client = ManualActivityCompletionClient(swf_client)
            with open('task_token.txt', 'r') as shared_file:
                task_token = shared_file.read()
            os.remove('task_token.txt')
            activities_client.complete('Manual Activity Done', task_token)


        wf_worker.run_once()
        act_executor.start(1, 4)
        time.sleep(5)

        activity_finisher = Thread(target=complete_this_activity)
        activity_finisher.start()
        activity_finisher.join()

        act_executor.stop()
        wf_worker.run_once()
        act_executor.join()
        wf_worker.run_once() 
        time.sleep(1)

        hist = self.get_workflow_execution_history()
        self.assertEqual(len(hist), 11)
        self.assertEqual(hist[-1]['eventType'], 'WorkflowExecutionCompleted')
        self.assertEqual(self.serializer.loads(
            hist[-1]['workflowExecutionCompletedEventAttributes']['result']), 'Manual Activity Done')


    def test_one_manual_one_automatic_activity(self):
        swf_client = self.client
        class OneManualOneAutomaticActivityWorkflow(WorkflowDefinition):
            def __init__(self, workflow_execution):
                super(OneManualOneAutomaticActivityWorkflow, self).__init__(workflow_execution)

            @execute(version='1.1', execution_start_to_close_timeout=60)
            def execute(self, template):
                (x, y) = yield ManualActivities.perform_task(template=template)
                arg_sum = yield BunchOfActivities.sum(x, y)
                return_(arg_sum)

        wf_worker = WorkflowWorker(
            self.session, self.region, self.domain, self.task_list, OneManualOneAutomaticActivityWorkflow)

        act_worker = ActivityWorker(
            self.session, self.region, self.domain, self.task_list,
            BunchOfActivities(), ManualActivities())

        with workflow_starter(self.session, self.region, self.domain, self.task_list):
            instance = OneManualOneAutomaticActivityWorkflow.execute(template='instructions.tmpl')
            self.workflow_execution = instance.workflow_execution

        def complete_this_activity():
            activities_client = ManualActivityCompletionClient(swf_client)
            with open('task_token.txt', 'r') as shared_file:
                task_token = shared_file.read()
            os.remove('task_token.txt')
            activities_client.complete((3,4), task_token)

        wf_worker.run_once()
        act_worker.run_once()

        time.sleep(5)
        activity_finisher = Thread(target=complete_this_activity)
        activity_finisher.start()
        activity_finisher.join()

        wf_worker.run_once()
        act_worker.run_once()
        wf_worker.run_once() 
        time.sleep(1)

        hist = self.get_workflow_execution_history()
        self.assertEqual(len(hist), 17)
        self.assertEqual(hist[-1]['eventType'], 'WorkflowExecutionCompleted')
        self.assertEqual(self.serializer.loads(
            hist[-1]['workflowExecutionCompletedEventAttributes']['result']), 7)

if __name__ == '__main__':
    unittest.main()
