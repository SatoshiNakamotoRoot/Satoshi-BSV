// Copyright (c) 2022 Bitcoin Association
// Distributed under the Open BSV software license, see the accompanying file
// LICENSE.

#pragma once

#include <iosfwd>

#include "uint256.h"
#include "span.h"
#include "miner_id/miner_info_error.h"

class block_bind
{
    uint256 mod_merkle_root_;
    uint256 prev_block_hash_;
    std::vector<uint8_t> sig_;

public:
    block_bind(const bsv::span<const uint8_t> mod_merkle_root,
               const bsv::span<const uint8_t> prev_block_hash,
               const bsv::span<const uint8_t> sig);

    const uint256& mm_root() const { return mod_merkle_root_; }
    const uint256& prev_block_hash() const { return prev_block_hash_; }
    
    auto cbegin_sig() const { return sig_.cbegin(); }
    auto cend_sig() const { return sig_.cend(); } 

    friend bool operator==(const block_bind&, const block_bind&);
    friend std::ostream& operator<<(std::ostream&, const block_bind&);
};

inline bool operator!=(const block_bind& a, const block_bind& b)
{
    return !(a == b);
}

bool verify(const block_bind&);

class miner_info_ref
{
    uint256 txid_{};
    class block_bind block_bind_;

  public:
    miner_info_ref(bsv::span<const uint8_t> txid, const block_bind&);

    const uint256& txid() const { return txid_; }
    const block_bind& blockbind() const { return block_bind_; }

    friend bool operator==(const miner_info_ref&, const miner_info_ref&);
    friend std::ostream& operator<<(std::ostream&, const miner_info_ref&); 
};

inline bool operator!=(const miner_info_ref& a, const miner_info_ref& b)
{
    return !(a == b);
}

std::variant<miner_info_ref, miner_info_error> ParseMinerInfoRef(
    const bsv::span<const uint8_t> script);


