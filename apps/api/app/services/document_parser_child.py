"""Untrusted parser process. Never import application settings/DB credentials here."""
import io
import json
import resource
import socket
import sys


def fail(code):
    print(json.dumps({'error': code}))
    raise SystemExit(0)


def main():
    mode, extension, raw_options = sys.argv[1:]
    options = json.loads(raw_options)
    memory = options['memory'] * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (options['seconds']+1, options['seconds']+1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (options['chars']*12+1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    # The parser never fetches links. Block Python socket creation as an extra guard.
    def no_network(*args, **kwargs):
        raise RuntimeError('Network access disabled')
    socket.socket = no_network
    data = sys.stdin.buffer.read(options['bytes']+1)
    if len(data) > options['bytes']:
        fail('limits')
    sources = []
    if extension == '.pdf':
        from pypdf import PdfReader, Configuration
        import pypdf
        cap = 8 * 1024 * 1024
        pypdf.overwrite_configuration(Configuration(maximum_declared_stream_length=cap,
            array_based_stream_maximum_output_length=cap, zlib_maximum_output_length=cap,
            lzw_maximum_output_length=cap, run_length_maximum_output_length=cap,
            brotli_maximum_output_length=cap, jbig2_maximum_output_length=cap,
            stream_decoding_work_maximum_length=32*1024*1024,
            stream_parsing_work_maximum_count=200000,
            page_tree_maximum_entries=options['pages']*10+100,
            page_tree_maximum_depth=30, xform_maximum_invocations_per_extraction=100,
            jbig2dec_binary=None))
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            fail('encrypted')
        if len(reader.pages) > options['pages']:
            fail('limits')
        count = 0
        for number, page in enumerate(reader.pages, 1):
            if mode == 'validate':
                continue
            text = (page.extract_text() or '').replace('\r\n','\n').replace('\r','\n')
            if '\x00' in text:
                fail('malformed')
            text.encode('utf-8', errors='strict')
            count += len(text)
            if count > options['chars']:
                fail('limits')
            sources.append({'text':text, 'page_number':number, 'markdown':False})
        if mode != 'validate' and not any(source['text'].strip() for source in sources):
            fail('ocr' if len(reader.pages) else 'empty')
    else:
        try:
            text = data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
        except UnicodeDecodeError:
            fail('encoding')
        if any(ord(c) < 32 and c not in '\n\t\f' for c in text):
            fail('binary')
        if len(text) > options['chars']:
            fail('limits')
        if not text.strip():
            fail('empty')
        sources.append({'text':text, 'page_number':None, 'markdown':extension == '.md'})
    print(json.dumps({'sources':sources}, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except MemoryError:
        fail('limits')
    except Exception:
        # Never send parser exception strings, input text or file paths to the API/log.
        fail('malformed')
