import copy
import re
from uuid import uuid4
from datetime import datetime, timezone
from bson import ObjectId

class MockCursor:
    def __init__(self, docs):
        self._docs = docs
        self._skip = 0
        self._limit = None

    def sort(self, key_or_list, direction=1):
        # basic sort support
        if isinstance(key_or_list, str):
            key = key_or_list
            rev = (direction == -1)
        elif isinstance(key_or_list, list) and key_or_list:
            key, direction = key_or_list[0]
            rev = (direction == -1)
        else:
            return self
        try:
            self._docs.sort(key=lambda d: d.get(key) or "", reverse=rev)
        except Exception:
            pass
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, length=None):
        docs = self._docs[self._skip:]
        lim = length if length is not None else self._limit
        if lim is not None:
            docs = docs[:lim]
        return [copy.deepcopy(d) for d in docs]

    def __aiter__(self):
        self._iter = iter(self._docs[self._skip:None if self._limit is None else self._skip + self._limit])
        return self

    async def __anext__(self):
        try:
            return copy.deepcopy(next(self._iter))
        except StopIteration:
            raise StopAsyncIteration


def _matches(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in expected):
                return False
            continue
        if key == "$and":
            if not all(_matches(doc, sub) for sub in expected):
                return False
            continue

        actual = doc.get(key)
        if isinstance(expected, dict):
            for op, val in expected.items():
                if op == "$ne" and actual == val:
                    return False
                elif op == "$eq" and actual != val:
                    return False
                elif op == "$in" and actual not in val:
                    return False
                elif op == "$nin" and actual in val:
                    return False
                elif op == "$exists":
                    exists = key in doc
                    if exists != bool(val):
                        return False
                elif op == "$lt" and not (actual is not None and actual < val):
                    return False
                elif op == "$lte" and not (actual is not None and actual <= val):
                    return False
                elif op == "$gt" and not (actual is not None and actual > val):
                    return False
                elif op == "$gte" and not (actual is not None and actual >= val):
                    return False
        elif actual != expected:
            return False
    return True


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = str(ObjectId())
        self.docs.append(d)
        res = type("InsertResult", (), {"inserted_id": d["_id"]})()
        return res

    async def insert_many(self, docs):
        res_ids = []
        for doc in docs:
            r = await self.insert_one(doc)
            res_ids.append(r.inserted_id)
        return type("InsertManyResult", (), {"inserted_ids": res_ids})()

    async def find_one(self, query=None, *args, **kwargs):
        query = query or {}
        for d in self.docs:
            if _matches(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, *args, **kwargs):
        query = query or {}
        matched = [d for d in self.docs if _matches(d, query)]
        return MockCursor(matched)

    async def count_documents(self, query=None):
        query = query or {}
        return sum(1 for d in self.docs if _matches(d, query))

    async def update_one(self, query, update, upsert=False):
        matched = None
        for d in self.docs:
            if _matches(d, query):
                matched = d
                break
        if not matched:
            if upsert:
                new_doc = copy.deepcopy(query)
                if "$set" in update:
                    new_doc.update(update["$set"])
                await self.insert_one(new_doc)
                return type("UpdateResult", (), {"matched_count": 0, "modified_count": 1, "upserted_id": True})()
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0, "upserted_id": None})()

        if "$set" in update:
            matched.update(copy.deepcopy(update["$set"]))
        return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1, "upserted_id": None})()

    async def update_many(self, query, update, upsert=False):
        count = 0
        for d in self.docs:
            if _matches(d, query):
                if "$set" in update:
                    d.update(copy.deepcopy(update["$set"]))
                count += 1
        return type("UpdateResult", (), {"matched_count": count, "modified_count": count})()

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if _matches(d, query):
                self.docs.pop(i)
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, query):
        orig_len = len(self.docs)
        self.docs = [d for d in self.docs if not _matches(d, query)]
        return type("DeleteResult", (), {"deleted_count": orig_len - len(self.docs)})()

    async def drop(self):
        self.docs.clear()

    async def create_index(self, *args, **kwargs):
        return "idx_created"

    async def create_indexes(self, *args, **kwargs):
        return ["idx_created"]

    def aggregate(self, pipeline):
        current_docs = [copy.deepcopy(d) for d in self.docs]
        for stage in pipeline:
            if "$match" in stage:
                current_docs = [d for d in current_docs if _matches(d, stage["$match"])]
            elif "$group" in stage:
                group_spec = stage["$group"]
                group_field = group_spec.get("_id")
                grouped = {}
                if isinstance(group_field, str) and group_field.startswith("$"):
                    key_attr = group_field[1:]
                    for d in current_docs:
                        val = d.get(key_attr)
                        grouped[val] = grouped.get(val, 0) + 1
                    current_docs = [{"_id": k, "count": v} for k, v in grouped.items()]
            elif "$sort" in stage:
                sort_spec = stage["$sort"]
                for sort_key, direction in sort_spec.items():
                    current_docs.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=(direction == -1))
        return MockCursor(current_docs)


class MockDatabase:
    def __init__(self, name="saas_monitor_test"):
        self.name = name
        self._collections = {}

    def __getitem__(self, item):
        if item not in self._collections:
            self._collections[item] = MockCollection(item)
        return self._collections[item]

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        return self[item]

    async def command(self, cmd, *args, **kwargs):
        return {"ok": 1.0}

    def drop_collection(self, name):
        if name in self._collections:
            self._collections[name].docs.clear()


class MockMongoClient:
    def __init__(self):
        self._dbs = {}
        self.admin = type("Admin", (), {"command": self._admin_cmd})()

    async def _admin_cmd(self, cmd, *args, **kwargs):
        return {"ok": 1.0}

    def __getitem__(self, item):
        if item not in self._dbs:
            self._dbs[item] = MockDatabase(item)
        return self._dbs[item]

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        return self[item]

    async def drop_database(self, name):
        if name in self._dbs:
            self._dbs[name]._collections.clear()

    def close(self):
        pass
