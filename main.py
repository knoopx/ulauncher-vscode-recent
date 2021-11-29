import os
import os.path
import json
import pathlib

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
	KeywordQueryEvent,
	ItemEnterEvent,
	PreferencesEvent,
	PreferencesUpdateEvent,
)
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from fuzzywuzzy import process, fuzz

import mimetypes

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

class Utils:
	@staticmethod
	def get_path(filename, from_home=False):
		base_dir = pathlib.Path.home() if from_home else pathlib.Path(
			__file__).parent.absolute()
		return os.path.join(base_dir, filename)

	@staticmethod
	def get_icon(f, size = 128):
		if os.path.isfile(f):
			content_type, _ = mimetypes.guess_type(f)
			if content_type:
				file_icon = Gio.content_type_get_icon(content_type)
				file_info = Gtk.IconTheme.get_default().choose_icon(file_icon.get_names(), size, 0)
				if file_info:
					return file_info.get_filename()
		else:
			file_info = Gtk.IconTheme.get_default().choose_icon(["folder"], size, 0)
			if file_info:
				return file_info.get_filename()



class Code:
	open_command_paths = ["/usr/bin/code", "/bin/code", "/snap/bin/code"]

	def get_installed_path(self):
		for path in self.open_command_paths:
			if os.path.exists(path):
				return path
		return False

	def is_installed(self):
		return bool(self.installed_path)

	def get_recents(self):
		recents = []
		storage = json.load(
			open(Utils.get_path(".config/Code/storage.json", True), "r"))
		openedPaths = storage["openedPathsList"]["entries"]
		for path in openedPaths:
			folder = "folderUri" in path
			uri = path["folderUri"] if folder else path["fileUri"]
			label = path["label"] if "label" in path else uri.split("/")[-1]
			recents.append({
				"folder": folder,
				"uri": uri,
				"path": Gio.Vfs.get_default().get_file_for_uri(uri).get_path(), #unquote_plus(urlparse(uri).path),
				"label": label
			})
		return recents

	def open_vscode(self, recent):
		if not self.is_installed():
			return
		option = "--folder-uri" if recent["folder"] else "--file-uri"
		os.system(f"{self.installed_path} {option} {recent['uri']}")

	def __init__(self):
		self.installed_path = self.get_installed_path()


class CodeExtension(Extension):
	keyword = None
	code = None

	def __init__(self):
		super(CodeExtension, self).__init__()
		self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
		self.subscribe(ItemEnterEvent, ItemEnterEventListener())
		self.subscribe(PreferencesEvent, PreferencesEventListener())
		self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())
		self.code = Code()

	def get_ext_result_items(self, query):
		query = query.lower() if query else ""
		recents = self.code.get_recents()
		items = []
		data = []
		label_matches = process.extract(query, choices=map(lambda c: c["label"], recents), limit=20, scorer=fuzz.partial_ratio)
		uri_matches = process.extract(query, choices=map(lambda c: c["uri"], recents), limit=20, scorer=fuzz.partial_ratio)
		for match in label_matches:
			recent = next((c for c in recents if c["label"] == match[0]), None)
			if (recent is not None and match[1] > 95):
				data.append(recent)
		for match in uri_matches:
			recent = next((c for c in recents if c["uri"] == match[0]), None)
			existing = next((c for c in data if c["uri"] == recent["uri"]), None)
			if (recent is not None and existing is None):
				data.append(recent)
		for recent in data[:20]:
			items.append(
				ExtensionResultItem(
					icon=Utils.get_icon(recent["path"]),
					name=recent["label"],
					description=recent["path"],
					on_enter=ExtensionCustomAction(recent),
				)
			)
		return items


class KeywordQueryEventListener(EventListener):
	def on_event(self, event, extension):
		items = []

		if not extension.code.is_installed():
			items.append(
				ExtensionResultItem(
					icon=Utils.get_path("images/icon.svg"),
					name="No VS Code?",
					description="Can't find the VS Code's `code` command in your system :(",
					highlightable=False,
					on_enter=HideWindowAction(),
				)
			)
			return RenderResultListAction(items)

		argument = event.get_argument() or ""
		items.extend(extension.get_ext_result_items(argument))
		return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
	def on_event(self, event, extension):
		recent = event.get_data()
		extension.code.open_vscode(recent)


class PreferencesEventListener(EventListener):
	def on_event(self, event, extension):
		extension.keyword = event.preferences["code_kw"]


class PreferencesUpdateEventListener(EventListener):
	def on_event(self, event, extension):
		if event.id == "code_kw":
			extension.keyword = event.new_value


if __name__ == "__main__":
	CodeExtension().run()
