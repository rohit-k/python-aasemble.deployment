import unittest

import mock

from testfixtures import log_capture

from aasemble.deployment.cloud import base, models


class CloudDriverTests(unittest.TestCase):
    def setUp(self):
        super(CloudDriverTests, self).setUp()
        self.driver = base.CloudDriver()

    @mock.patch('aasemble.deployment.cloud.base.get_driver')
    @log_capture()
    def test_connection(self, get_driver, log):
        class TestDriver(base.CloudDriver):
            provider = mock.sentinel.provider
            name = 'Test Cloud'

            def _get_driver_args_and_kwargs(self):
                return ((1, 2), {'foo': 'bar'})

        cloud_driver = TestDriver()

        self.assertEqual(cloud_driver.connection, get_driver.return_value.return_value)

        get_driver.assert_called_with(mock.sentinel.provider)
        get_driver(mock.sentinel.provider).assert_called_with(1, 2, foo='bar')
        log.check(('aasemble.deployment.cloud.base', 'INFO', 'Connecting to Test Cloud'))

    def test_detect_resources(self):
        node1 = models.Node(name='node1',
                            flavor='n1-standard-4',
                            image='ubuntu1404-12345678',
                            networks=[],
                            disk=20)

        node2 = models.Node(name='node2',
                            flavor='n1-standard-4',
                            image='ubuntu1404-12345678',
                            networks=[],
                            disk=20)

        node1.security_group_names = set(['webapp', 'ssh'])
        node2.security_group_names = set(['webapp'])

        sg_webapp = models.SecurityGroup(name='webapp')
        sg_ssh = models.SecurityGroup(name='ssh')

        sgr_https = models.SecurityGroupRule(security_group=sg_webapp,
                                             source_ip='0.0.0.0/0',
                                             from_port=443,
                                             to_port=443,
                                             protocol='tcp')

        sgr_ssh = models.SecurityGroupRule(security_group=sg_ssh,
                                           source_ip='0.0.0.0/0',
                                           from_port=22,
                                           to_port=22,
                                           protocol='tcp')

        class TestDriver(base.CloudDriver):
            def detect_nodes(self):
                return set([node1, node2])

            def detect_firewalls(self):
                return (set([sg_webapp, sg_ssh]), set([sgr_https, sgr_ssh]))

        cloud_driver = TestDriver()
        collection = cloud_driver.detect_resources()

        self.assertIn(node1, collection.nodes)
        self.assertIn(node2, collection.nodes)

        self.assertIn(sg_webapp, collection.nodes['node1'].security_groups)
        self.assertIn(sg_ssh, collection.nodes['node1'].security_groups)

        self.assertIn(sg_webapp, collection.nodes['node2'].security_groups)

        self.assertIn(sg_webapp, collection.security_groups)
        self.assertIn(sg_ssh, collection.security_groups)

        self.assertIn(sgr_https, collection.security_group_rules)
        self.assertIn(sgr_ssh, collection.security_group_rules)

    def test_is_node_relevant(self):
        class Node(object):
            def __init__(self, name, namespace=None):
                self.name = name
                self.namespace = namespace

        class TestDriver(base.CloudDriver):
            def get_namespace(self, node):
                return node.namespace

        cloud_driver = TestDriver()

        self.assertTrue(cloud_driver._is_node_relevant(Node('node1')), 'No namespace set, but node ignored')
        self.assertTrue(cloud_driver._is_node_relevant(Node('node1', namespace='something')), 'No namespace set, but node ignored')

        cloud_driver.namespace = 'testns'
        self.assertFalse(cloud_driver._is_node_relevant(Node('node1')), 'Namespace set, yet node with no namespace considered relevant')
        self.assertFalse(cloud_driver._is_node_relevant(Node('node1', namespace='something')), 'Namespace set, yet node with other namespace considered relevant')
        self.assertTrue(cloud_driver._is_node_relevant(Node('node1', namespace='testns')), 'Namespace set, yet node with correct namespace ignored')
        self.assertFalse(cloud_driver._is_node_relevant(Node('node1', namespace='testns1')), 'Namespace set, yet node with similar namespace considered relevant')

    def test_detect_nodes_converts_to_aasemble_nodes_from_provider_nodes(self):
        class TestDriver(base.CloudDriver):
            def _get_relevant_nodes(self):
                return [mock.sentinel.node1, mock.sentinel.node2]

            def _aasemble_node_from_provider_node(self, node):
                node.converted = True
                return node

        cloud_driver = TestDriver()

        nodes = list(cloud_driver.detect_nodes())

        self.assertEqual(len(nodes), 2)
        self.assertTrue(mock.sentinel.node1.converted)
        self.assertTrue(mock.sentinel.node2.converted)

    def test_apply_resources(self):
        self.created_nodes = []
        self.created_security_groups = []
        self.created_security_group_rules = []

        class TestDriver(base.CloudDriver):
            def create_node(selff, node):
                self.created_nodes += [node]

            def create_security_group(selff, security_group):
                self.created_security_groups += [security_group]

            def create_security_group_rule(selff, security_group_rule):
                self.created_security_group_rules += [security_group_rule]

        class Collection(object):
            nodes = set([mock.sentinel.node1, mock.sentinel.node2])
            security_groups = set([mock.sentinel.sg1, mock.sentinel.sg2])
            security_group_rules = set([mock.sentinel.sgr1, mock.sentinel.sgr2])

        collection = Collection()

        cloud_driver = TestDriver()

        cloud_driver.apply_resources(collection)

        self.assertIn(mock.sentinel.node1, self.created_nodes)
        self.assertIn(mock.sentinel.node2, self.created_nodes)
        self.assertIn(mock.sentinel.sg1, self.created_security_groups)
        self.assertIn(mock.sentinel.sg2, self.created_security_groups)
        self.assertIn(mock.sentinel.sgr1, self.created_security_group_rules)
        self.assertIn(mock.sentinel.sgr2, self.created_security_group_rules)
