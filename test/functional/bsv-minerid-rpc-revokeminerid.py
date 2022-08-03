#!/usr/bin/env python3
# Copyright (c) 2022 Bitcoin Association
# Distributed under the Open BSV software license, see the accompanying file LICENSE.

from test_framework.test_framework import BitcoinTestFramework
from test_framework.mininode import msg_block, NodeConnCB, sha256
from test_framework.blocktools import MinerIDParams, make_miner_id_block
from test_framework.util import create_confirmed_utxos, wait_until, bytes_to_hex_str, assert_raises_rpc_error
from decimal import Decimal

from bip32utils import BIP32Key

import ecdsa
import os

'''
Test handling of the MinerID revokeminerid RPC interface.
'''
class RovokeMinerIdRpc(BitcoinTestFramework):

    def set_test_params(self):
        self.num_nodes = 3
        self.setup_clean_chain = True
        self.extra_args = [['-whitelist=127.0.0.1']] * self.num_nodes
        self.curve = ecdsa.SECP256k1

        # Setup miner ID keys
        self.minerIdKeys = []
        for i in range(4):
            bip32key = BIP32Key.fromEntropy(os.urandom(16))
            key = {
                "public" : bip32key.PublicKey(),
                "signing" : ecdsa.SigningKey.from_string(bip32key.PrivateKey(), curve=self.curve)
            }
            self.minerIdKeys.append(key)

        # And a single revocation key
        minerIdRevocationKey = BIP32Key.fromEntropy(os.urandom(16))
        self.minerIdRevocationPubKey = minerIdRevocationKey.PublicKey()
        self.minerIdRevocationSigningKey = ecdsa.SigningKey.from_string(minerIdRevocationKey.PrivateKey(), curve=self.curve)

    def setup_network(self):
        self.add_nodes(self.num_nodes)

    def make_revokeminerid_input(self):
        compromisedMinerId = self.minerIdKeys[0]["public"]
        hashCompromisedMinerId = sha256(compromisedMinerId)
        # Make revoke minerId rpc input.
        inputDoc = {
            "revocationKey": bytes_to_hex_str(self.minerIdRevocationPubKey),
            "minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]),
            "revocationMessage": {
                "compromised_minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"])
            },
            "revocationMessageSig": {
                "sig1": bytes_to_hex_str(self.minerIdRevocationSigningKey.sign_digest(hashCompromisedMinerId, sigencode=ecdsa.util.sigencode_der)),
                "sig2": bytes_to_hex_str(self.minerIdKeys[0]["signing"].sign_digest(hashCompromisedMinerId, sigencode=ecdsa.util.sigencode_der))
            }
        }
        return inputDoc

    def test_invalid_input(self, conn):
        assert_raises_rpc_error(-3, "Expected type object, got string", conn.rpc.revokeminerid, "")
        assert_raises_rpc_error(-3, "Expected type object, got array", conn.rpc.revokeminerid, [])
        assert_raises_rpc_error(-8, "Invalid parameter: An empty json object", conn.rpc.revokeminerid, {})
        assert_raises_rpc_error(
            -8, "Invalid revocationKey key!", conn.rpc.revokeminerid,
                {
                    "revocationKey": "1",
                    "minerId": "1",
                    "revocationMessage": {
                        "compromised_minerId": "1"
                    },
                    "revocationMessageSig": {
                        "sig1": "1",
                        "sig2": "1"
                    }
                })
        assert_raises_rpc_error(
            -8, "Invalid minerId key!", conn.rpc.revokeminerid,
                {
                    "revocationKey": bytes_to_hex_str(self.minerIdRevocationPubKey),
                    "minerId": "1",
                    "revocationMessage": {
                        "compromised_minerId": "1"
                    },
                    "revocationMessageSig": {
                        "sig1": "1",
                        "sig2": "1"
                    }
                })
        assert_raises_rpc_error(
            -8, "Invalid compromised_minerId key!", conn.rpc.revokeminerid,
                {
                    "revocationKey": bytes_to_hex_str(self.minerIdRevocationPubKey),
                    "minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]),
                    "revocationMessage": {
                        "compromised_minerId": "1"
                    },
                    "revocationMessageSig": {
                        "sig1": "1",
                        "sig2": "1"
                    }
                })
        assert_raises_rpc_error(
            -8, "Invalid sig1 signature!", conn.rpc.revokeminerid,
                {
                    "revocationKey": bytes_to_hex_str(self.minerIdRevocationPubKey),
                    "minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]),
                    "revocationMessage": {
                        "compromised_minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]) 
                    },
                    "revocationMessageSig": {
                        "sig1": "1",
                        "sig2": "1"
                    }
                })
        compromisedMinerId = self.minerIdKeys[0]["public"]
        hashCompromisedMinerId = sha256(compromisedMinerId)
        assert_raises_rpc_error(
            -8, "Invalid sig2 signature!", conn.rpc.revokeminerid,
                {
                    "revocationKey": bytes_to_hex_str(self.minerIdRevocationPubKey),
                    "minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]),
                    "revocationMessage": {
                        "compromised_minerId": bytes_to_hex_str(self.minerIdKeys[0]["public"]) 
                    },
                    "revocationMessageSig": {
                        "sig1": bytes_to_hex_str(self.minerIdRevocationSigningKey.sign_digest(hashCompromisedMinerId, sigencode=ecdsa.util.sigencode_der)),
                        "sig2": "1"
                    }
                })

    def run_test(self):

        with self.run_all_nodes_connected(title="revokeminerid_rpc", args=self.extra_args, p2pConnections=[0,1,2]) as (p2p_0,p2p_1,p2p_2):

            # Get out of IBD and make some spendable outputs
            utxos = create_confirmed_utxos(Decimal("250") / 100000000, self.nodes[0], 5, nodes=self.nodes)

            # Produce a miner ID chain with 2 rotated keys and a current key
            minerIdParams = MinerIDParams(blockHeight = self.nodes[0].getblockcount() + 1,
                                          minerId = self.minerIdKeys[0]["signing"],
                                          minerIdPub = self.minerIdKeys[0]["public"],
                                          revocationKey = self.minerIdRevocationSigningKey,
                                          revocationKeyPub = self.minerIdRevocationPubKey)
            block = make_miner_id_block(p2p_0, minerIdParams, utxos.pop())
            p2p_0.send_message(msg_block(block))
            wait_until(lambda: self.nodes[0].getbestblockhash() == block.hash)

            minerIdParams = MinerIDParams(blockHeight = self.nodes[0].getblockcount() + 1,
                                          minerId = self.minerIdKeys[1]["signing"],
                                          minerIdPub = self.minerIdKeys[1]["public"],
                                          prevMinerId = self.minerIdKeys[0]["signing"],
                                          prevMinerIdPub = self.minerIdKeys[0]["public"],
                                          revocationKey = self.minerIdRevocationSigningKey,
                                          revocationKeyPub = self.minerIdRevocationPubKey)
            block = make_miner_id_block(p2p_0, minerIdParams, utxos.pop())
            p2p_0.send_message(msg_block(block))
            wait_until(lambda: self.nodes[0].getbestblockhash() == block.hash)
            
            minerIdParams = MinerIDParams(blockHeight = self.nodes[0].getblockcount() + 1,
                                          minerId = self.minerIdKeys[2]["signing"],
                                          minerIdPub = self.minerIdKeys[2]["public"],
                                          prevMinerId = self.minerIdKeys[1]["signing"],
                                          prevMinerIdPub = self.minerIdKeys[1]["public"],
                                          revocationKey = self.minerIdRevocationSigningKey,
                                          revocationKeyPub = self.minerIdRevocationPubKey)
            block = make_miner_id_block(p2p_0, minerIdParams, utxos.pop())
            p2p_0.send_message(msg_block(block))
            wait_until(lambda: self.nodes[0].getbestblockhash() == block.hash)

            self.sync_all()

            assert(self.nodes[0].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'CURRENT')
            assert(self.nodes[1].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'CURRENT')
            assert(self.nodes[2].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'CURRENT')

            self.nodes[0].revokeminerid(self.make_revokeminerid_input())

            wait_until(lambda: self.nodes[0].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'REVOKED')
            wait_until(lambda: self.nodes[1].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'REVOKED')
            wait_until(lambda: self.nodes[2].dumpminerids()['miners'][0]['minerids'][0]['state'] == 'REVOKED')
    
            self.test_invalid_input(p2p_0)

if __name__ == '__main__':
    RovokeMinerIdRpc().main()

