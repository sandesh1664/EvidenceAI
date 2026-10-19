from dataclasses import dataclass
import re
from uuid import UUID, uuid5


@dataclass(frozen=True)
class Chunk:
    id: UUID
    document_id: UUID
    workspace_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
    source_ref: str
    char_start: int
    char_end: int


def chunk_sources(sources, document_id: UUID, workspace_id: UUID, *, size=1600, overlap=200, max_chunks=10000):
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError('Invalid chunk limits')
    chunks = []
    for source in sources:
        text, page = source['text'], source['page_number']
        boundaries = [(0, None)]
        if source.get('markdown'):
            for match in re.finditer(r'^#{1,6} +(.+)$', text, flags=re.MULTILINE):
                if match.start() == 0:
                    boundaries[0] = (0, match.group(1).strip()[:200])
                else:
                    boundaries.append((match.start(), match.group(1).strip()[:200]))
        for part, (start, section) in enumerate(boundaries):
            end = boundaries[part+1][0] if part+1 < len(boundaries) else len(text)
            position = start
            while position < end:
                stop = min(position+size, end)
                content = text[position:stop]
                if content.strip():
                    index = len(chunks)
                    if index >= max_chunks:
                        raise ValueError('Too many document chunks')
                    chunks.append(Chunk(uuid5(document_id,str(index)),document_id,workspace_id,index,content,page,section,
                        f'document:{document_id}' + (f'/page:{page}' if page else ''),position,stop))
                if stop == end:
                    break
                position += size-overlap
    return chunks
