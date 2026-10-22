// Modified 2026-10-22 by Qingliang community: bounded VBA decompression and module offsets.
/*
 * (c) Copyright Ascensio System SIA 2010-2023
 *
 * This program is a free software product. You can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public License (AGPL)
 * version 3 as published by the Free Software Foundation. In accordance with
 * Section 7(a) of the GNU AGPL its Section 15 shall be amended to the effect
 * that Ascensio System SIA expressly excludes the warranty of non-infringement
 * of any third-party rights.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the implied
 * warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR  PURPOSE. For
 * details, see the GNU AGPL at: http://www.gnu.org/licenses/agpl-3.0.html
 *
 * You can contact Ascensio System SIA at 20A-6 Ernesta Birznieka-Upish
 * street, Riga, Latvia, EU, LV-1050.
 *
 * The  interactive user interfaces in modified source and object code versions
 * of the Program must display Appropriate Legal Notices, as required under
 * Section 5 of the GNU AGPL version 3.
 *
 * Pursuant to Section 7(b) of the License you must retain the original Product
 * logo when distributing the program. Pursuant to Section 7(e) we decline to
 * grant you any rights under trademark law for use of our trademarks.
 *
 * All the Product's GUI elements, including illustrations and icon sets, as
 * well as technical writing content are licensed under the terms of the
 * Creative Commons Attribution-ShareAlike 4.0 International. See the License
 * terms at http://creativecommons.org/licenses/by-sa/4.0/legalcode
 *
 */

#include "VbaBinary.h"

#include <boost/bind.hpp>

#include <algorithm>
#include <sstream>



CVbaFile::~CVbaFile()
{
	streams.clear();

	if (storage_)delete storage_;
	storage_ = NULL;
}

bool CVbaFile::isError()
{
	if (storage_ != NULL) return false;
	return true;
}

bool CVbaFile::Open(const std::wstring & file_path)
{
	if (storage_) delete storage_;
	storage_ = NULL;

	storage_ = new POLE::Storage(file_path.c_str());
	if (storage_ == NULL) return false;

	if (storage_->open(false, false) == false)
	{
		delete storage_;
		storage_ = NULL;
	}

	if (storage_ == NULL) return false;
	return true;
}
CVbaFile::CVbaFile(const std::wstring & file_path)
{
	storage_ = NULL;
	Open(file_path);
}
CVbaFileStreamPtr CVbaFile::getNamedStream(const std::wstring& name, _UINT32 offset)
{
	if (!streams[name])
	{
		POLE::Stream * pStream = openStream(name.c_str());
		if (pStream)
			streams[name].reset(new CVbaFileStream(pStream, offset));
	}
	return streams[name];
}

void CVbaFile::closeNamedStream(const std::wstring& name)
{
	streams[name].reset();
}

POLE::Stream* CVbaFile::openStream(const std::wstring & stream_name)
{
	if (storage_ == NULL) return NULL;

	POLE::Stream* pStream = new POLE::Stream(storage_, stream_name);
	if (pStream == NULL)
	{
		return NULL;
	}
	if ((pStream) && (pStream->size() > 0))
		return pStream;
	else return NULL;
}
const unsigned char VBASTREAM_SIGNATURE = 1;

const _UINT16 CHUNK_SIGMASK = 0x7000;
const _UINT16 CHUNK_SIG = 0x3000;
const _UINT16 CHUNK_COMPRESSED = 0x8000;
const _UINT16 CHUNK_LENMASK = 0x0FFF;

inline _UINT16 extract(_UINT16 nBitField, unsigned char nStartBit, unsigned char nBitCount)
{
	_UINT64 nMask = 1; nMask <<= nBitCount; --nMask;
	return static_cast< _UINT16 >(nMask & (nBitField >> nStartBit));
}
CVbaFileStream::CVbaFileStream(POLE::Stream* stream, _UINT32 offset)
{
    if (!stream || offset >= stream->size())
        return;
    const size_t size = static_cast<size_t>(stream->size() - offset);
    std::vector<unsigned char> data(size);
    stream->seek(offset);
    if (stream->read(data.data(), size) != size)
        return;
    if (data[0] != VBASTREAM_SIGNATURE)
    {
        arrChunks.swap(data);
        return;
    }

    // MS-OVBA 2.4.1: bounded chunks and copy tokens; publish only complete output.
    std::vector<unsigned char> decoded;
    size_t current = 1;
    while (current < data.size())
    {
        if (data.size() - current < 2)
            return;
        const _UINT16 header = data[current] | (static_cast<_UINT16>(data[current + 1]) << 8);
        current += 2;
        const size_t payload = (header & CHUNK_LENMASK) + 1;
        if ((header & CHUNK_SIGMASK) != CHUNK_SIG || payload > data.size() - current)
            return;
        const size_t end = current + payload;
        std::vector<unsigned char> chunk;
        if (!(header & CHUNK_COMPRESSED))
        {
            if (payload != 4096)
                return;
            chunk.insert(chunk.end(), data.begin() + current, data.begin() + end);
            current = end;
        }
        else
        {
            while (current < end)
            {
                const unsigned char flags = data[current++];
                for (unsigned bit = 0; bit < 8 && current < end; ++bit)
                {
                    if (flags & (1u << bit))
                    {
                        if (end - current < 2)
                            return;
                        const _UINT16 token = data[current] | (static_cast<_UINT16>(data[current + 1]) << 8);
                        current += 2;
                        unsigned bits = 4;
                        while ((static_cast<size_t>(1) << bits) < chunk.size())
                            ++bits;
                        const unsigned mask = 0xffffu >> bits;
                        const size_t length = (token & mask) + 3;
                        const size_t distance = (token >> (16 - bits)) + 1;
                        if (distance > chunk.size() || length > 4096 - chunk.size())
                            return;
                        for (size_t i = 0; i < length; ++i)
                            chunk.push_back(chunk[chunk.size() - distance]);
                    }
                    else
                    {
                        if (chunk.size() == 4096)
                            return;
                        chunk.push_back(data[current++]);
                    }
                }
            }
        }
        decoded.insert(decoded.end(), chunk.begin(), chunk.end());
    }
    arrChunks.swap(decoded);
}
CVbaFileStream::~CVbaFileStream()
{
	arrChunks.clear();
}
void CVbaFileStream::read(void* buf, size_t size)
{
    if (!buf || pos >= arrChunks.size())
        return;
    size = (std::min)(size, arrChunks.size() - pos);
    memcpy(buf, arrChunks.data() + pos, size);
    pos += size;
}
