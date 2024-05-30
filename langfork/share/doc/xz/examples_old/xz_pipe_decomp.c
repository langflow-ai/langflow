/*
 * xz_pipe_decomp.c
 * A simple example of pipe-only xz decompressor implementation.
 * version: 2012-06-14 - by Daniel Mealha Cabrita
 * Not copyrighted -- provided to the public domain.
 *
 * Compiling:
 * Link with liblzma. GCC example:
 * $ gcc -llzma xz_pipe_decomp.c -o xz_pipe_decomp
 *
 * Usage example:
 * $ cat some_file.xz | ./xz_pipe_decomp > some_file
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdbool.h>
#include <lzma.h>


/* read/write buffer sizes */
#define IN_BUF_MAX	4096
#define OUT_BUF_MAX	4096

/* error codes */
#define RET_OK			0
#define RET_ERROR_INIT		1
#define RET_ERROR_INPUT		2
#define RET_ERROR_OUTPUT	3
#define RET_ERROR_DECOMPRESSION	4


/* note: in_file and out_file must be open already */
int xz_decompress (FILE *in_file, FILE *out_file)
{
	lzma_stream strm = LZMA_STREAM_INIT; /* alloc and init lzma_stream struct */
	const uint32_t flags = LZMA_TELL_UNSUPPORTED_CHECK | LZMA_CONCATENATED;
	const uint64_t memory_limit = UINT64_MAX; /* no memory limit */
	uint8_t in_buf [IN_BUF_MAX];
	uint8_t out_buf [OUT_BUF_MAX];
	size_t in_len;	/* length of useful data in in_buf */
	size_t out_len;	/* length of useful data in out_buf */
	bool in_finished = false;
	bool out_finished = false;
	lzma_action action;
	lzma_ret ret_xz;
	int ret;

	ret = RET_OK;

	/* initialize xz decoder */
	ret_xz = lzma_stream_decoder (&strm, memory_limit, flags);
	if (ret_xz != LZMA_OK) {
		fprintf (stderr, "lzma_stream_decoder error: %d\n", (int) ret_xz);
		return RET_ERROR_INIT;
	}

	while ((! in_finished) && (! out_finished)) {
		/* read incoming data */
		in_len = fread (in_buf, 1, IN_BUF_MAX, in_file);

		if (feof (in_file)) {
			in_finished = true;
		}
		if (ferror (in_file)) {
			in_finished = true;
			ret = RET_ERROR_INPUT;
		}

		strm.next_in = in_buf;
		strm.avail_in = in_len;

		/* if no more data from in_buf, flushes the
		   internal xz buffers and closes the decompressed data
		   with LZMA_FINISH */
		action = in_finished ? LZMA_FINISH : LZMA_RUN;

		/* loop until there's no pending decompressed output */
		do {
			/* out_buf is clean at this point */
			strm.next_out = out_buf;
			strm.avail_out = OUT_BUF_MAX;

			/* decompress data */
			ret_xz = lzma_code (&strm, action);

			if ((ret_xz != LZMA_OK) && (ret_xz != LZMA_STREAM_END)) {
				fprintf (stderr, "lzma_code error: %d\n", (int) ret_xz);
				out_finished = true;
				ret = RET_ERROR_DECOMPRESSION;
			} else {
				/* write decompressed data */
				out_len = OUT_BUF_MAX - strm.avail_out;
				fwrite (out_buf, 1, out_len, out_file);
				if (ferror (out_file)) {
					out_finished = true;
					ret = RET_ERROR_OUTPUT;
				}
			}
		} while (strm.avail_out == 0);
	}

	/* Bug fix (2012-06-14): If no errors were detected, check
	   that the last lzma_code() call returned LZMA_STREAM_END.
	   If not, the file is probably truncated. */
	if ((ret == RET_OK) && (ret_xz != LZMA_STREAM_END)) {
		fprintf (stderr, "Input truncated or corrupt\n");
		ret = RET_ERROR_DECOMPRESSION;
	}

	lzma_end (&strm);
	return ret;
}

int main ()
{
	int ret;

	ret = xz_decompress (stdin, stdout);
	return ret;
}

