import vk_api
import time
import json
import os
import requests
import transliterate
import pandas as pd

from langdetect import detect
from pprint import pprint
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType



# МЕТОДЫ API
#________________________________________________________________________________

# авторизация на сайте
def auth(token, group_id):
    vk = vk_api.VkApi(token = token)
    longpoll = VkBotLongPoll(vk, group_id)
    vk = vk.get_api()
    return vk, longpoll


# создаём историю переписки
def chat_history(peer_id, id_, d):
	d_id[peer_id] = {'id': id_, 'd': d}


# собираем инфу о подписчиках (где key - имя, а val - id)
def get_user_ids(user_ids): # user_ids - массив id
	d = {'name': [''], 'id': [''], 'link': ['']}
	for u in vk.users.get(user_ids = user_ids):
		d['name'].append(transliterate_word(u['first_name'] + ' ' + u['last_name']))
		d['id'].append(u['id'])
		d['link'].append("vk.com/id" + str(u['id']))
	return d



# ЧТЕНИЕ, ЗАПИСЬ И РАБОТА С ФАЙЛАМИ
#________________________________________________________________________________

class WRITE:

	def __init__(self, file_name, d):
		self.file_name = file_name
		self.d = d

	def write_json(self):
		json.dump(self.d, open(self.file_name, "w", encoding = "utf-8"), ensure_ascii = False)

	def write_xlsx(self):
		writer = pd.ExcelWriter("user_ids.xlsx", engine = 'xlsxwriter')
		for sheet_name in self.d['sheet_names']:
			d_write_xlsx = self.d[sheet_name]
			df = pd.DataFrame(d_write_xlsx)			
			df.to_excel(writer, sheet_name = sheet_name, index = False)

			workbook  = writer.book
			worksheet = writer.sheets[sheet_name]
			format1 = workbook.add_format({'num_format': '0'})
			worksheet.set_column('B:B', None, format1)

			# автоматическое настраивание ширины колонок
			for idx, col in enumerate(df): 
			        series = df[col]
			        max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) + 1 
			        worksheet.set_column(idx, idx, max_len)

		writer.save()
	

# на основе расширения будет по разному обрабатывать файл
def save_with_ext(d_write):
	ext = settings['options']['file_ext']
	file_name_ext = 'user_ids' + ext
	if 'json' in ext:
		WRITE(file_name_ext, d_write).write_json()
	elif 'xlsx' in ext:
		WRITE(file_name_ext, d_write).write_xlsx()


class READ:

	def __init__(self, file_name):
		self.file_name = file_name

	def read_json(self):
		try:
			return json.loads(open(self.file_name, 'r', encoding = "utf-8").read())
		except json.decoder.JSONDecodeError:
			return {}

	def read_xlsx(self):
		d_read = {'sheet_names': []}
		colomn_names = ('name', 'id', 'link')
		xlsx_read = pd.read_excel(pd.ExcelFile(self.file_name), None)
		for sheet_name, val in xlsx_read.items():
			d_read['sheet_names'].append(sheet_name)
			d_one_list = val.to_dict(orient = 'list')
			for col_name in colomn_names:
				if col_name not in d_one_list:
					d_one_list[col_name] = []
			d_read[sheet_name] = d_one_list

		for sheet_name in d_read['sheet_names']:
			val = d_read[sheet_name]['id']
			for id_number in val:
				if pd.isnull(id_number):
					ind = val.index(id_number)
					link = d_read[sheet_name]['link'][ind]
					if not pd.isnull(link) and 'vk.com/' in link:
						d_read[sheet_name]['id'][ind] = link.split('/')[-1]
		return d_read
	
	def read(self):
		d_xlsx = ''
		ext = settings['options']['file_ext']
		if 'json' in ext:
			d_xlsx = READ(self.file_name).read_json()
		elif 'xlsx' in ext:
			d_xlsx = READ(self.file_name).read_xlsx()

		return d_xlsx


def download_file(file_name, url): 
	open(file_name, "wb").write(requests.get(url).content) 



settings = READ('settings.json').read_json()



# СОЗДАНИЕ КЛАВИАТУР
#____________________________________________________________________________________

def create_keyboard(type_ ,a, color = settings['options']['keyboard']['color']):
	keyboard = {"one_time": False, "buttons": []}
	for i in a:
		s = []
		for j in i:
			button = {"action": {"type": type_, "label": j}}
			s.append(button)
		keyboard['buttons'].append(s)
	return keyboard


def create_rows_in_mas(a, count_rows = 0, count_colomns = 0):
	return [[i] for i in a]



# СОЗДАНИЕ И ПРЕОБРАЗОВАНИЕ ПЕРЕМЕННЫХ
#________________________________________________________________________________

# преобразует имена в латинице на русскую раскладку
def transliterate_word(s):
	lang = detect(s)
	if lang != 'ru':
		s = transliterate.translit(s, 'ru')
		if 'ы' in s:
			s = s.replace('ы', 'й')
			if 'йо' in s:
				s = s.replace('йо', 'ё')
	return s


# возращает строку "название файла" + "расширение"
def create_file_name(title, ext):
	ext = '.' + ext
	if title[-len(ext):] == ext:
		return title
	return title + ext


# создаёт словарь d с параметрами отправки
def create_d(peer_id, text, keyboard = {"buttons":[], "one_time": True, "inline": False}):
	if not settings['options']['keyboard']['using']:
		keyboard = {"buttons":[], "one_time": True, "inline": False}
	return {'attachments': [],
			'peer_id': peer_id, 
			'spare_peer_id': peer_id, 
			'text': text, 
			'lat': 0, 
			'long': 0,
			'sticker_id': 0,
			'keyboard': keyboard}



# ОБРАБОТКА ИВЕНТОВ И ВЛОЖЕНИЙ
#________________________________________________________________________________

def reply(message):
	while True:
		if 'reply_message' in message:
			id_ = message['reply_message']['id']
			message = vk.messages.getById(message_ids = id_)['items'][0]
		elif 'fwd_messages' in message:
			if len(message['fwd_messages']) > 1:
				return False
			elif message['fwd_messages'] != []:
				message = message['fwd_messages'][0]
			else:
				return message
		else:
			return message


def get_default_attach(type_, a, owner_id = 'owner_id', id_ = 'id'):
	owner_id = a[owner_id]
	if owner_id >= 2000000000:
		owner_id = owner_id * -1
	s = type_ + str(owner_id) + '_' + str(a[id_])
	if 'access_key' in a:
		s += '_' + a['access_key']
	return s


def docs(type_, real_type_, peer_id, a):
	url = a['url']
	if 'title' in a and 'ext' in a:
		title = a['title']
		ext = a['ext']
	else:
		title = real_type_
		if real_type_ == 'graffiti':
			type_ = 'doc'
			ext = 'png'
		elif real_type_ == 'audio_message':
			ext = 'mp3'
			url = a['link_mp3']
		else:
			return ''

	file_name = create_file_name(title, ext) # составляем название файла с расширением
	download_file(file_name, url) # скачиваем

	upload_url = vk.docs.getMessagesUploadServer(type = type_, peer_id = peer_id)['upload_url'] # ссылка для загрузки
	response = requests.post(upload_url, files = {'file': open(file_name, 'rb')}) # делаем POST-запрос
	result = json.loads(response.text)

	a = vk.docs.save(file = result['file'], title = title, tags = [])[real_type_] # получаем данные для отправки
	attach = get_default_attach(type_, a)

	if not settings['options']['upload_files']:
		os.remove(file_name)

	return attach


def get_attachments(peer_id, message):
	d = create_d(peer_id, message['text'])
	types = []
	type_video_flag = False

	if 'geo' in message:
		g = message['geo']['coordinates']
		d['lat'] = g['latitude']
		d['long'] = g['longitude']

	for attachment in message['attachments']:
		type_ = attachment['type']
		types.append(type_)
		a = attachment[type_]

		if type_ in ('photo', 'video', 'audio', 'wall_reply', 'market', 'market_album'):
			attach = get_default_attach(type_, a)
			if type_ in 'video':
				type_video_flag = True
			if type_ in 'audio' and type_video_flag: # если видео и аудио в одном сообщении
				d['attachments'].insert(0, attach) # добавляем аудио-вложение в начало массива
				continue
			
		elif 'wall' in type_:
			attach = get_default_attach(type_, a, owner_id = 'to_id')

		# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
		elif 'link' in type_:
			#pprint(a)
			attach = a['url']

		elif 'sticker' in type_:
			d['sticker_id'] = a['sticker_id']
			break

		elif type_ in ('doc', 'graffiti', 'audio_message'):
			real_type_ = type_
			attach = docs(type_, real_type_, peer_id, a)

		d['attachments'].append(attach)

	return d


def check_compliance(text, command):
	if text.lower() == command.lower():
		return True
	return False


def message_command(peer_id, text):
	if check_compliance(text, settings['options']['commands']['close_keydoard']):
		if not settings['options']['keyboard']['using']:
			answer = 'Кнопки уже не работают'
		else:
			answer = 'Кнопки больше не будут отображаться'
		settings['options']['keyboard']['using'] = False
		return create_d(peer_id, answer)

	elif check_compliance(text, settings['options']['commands']['open_keydoard']):
		if settings['options']['keyboard']['using']:
			answer = 'Кнопки уже работают'
		else:
			answer = 'Кнопки снова активированы'
		settings['options']['keyboard']['using'] = True
		return create_d(peer_id, answer, keyboard = keyboard_default_with_start)

	elif check_compliance(text, settings['options']['commands']['get_user_ids']):
		def start():
			global user_ids
			user_ids_group = vk.groups.getMembers(group_id = settings['vk_bot']['group_id'])['items']
			d_write = get_user_ids(user_ids_group)
			save_with_ext(d_write)
		start()
		answer = 'ID всех участников группы были сохранены в файл ' + '*user_ids' + settings['options']['file_ext'] + '*'
		return create_d(peer_id, answer, keyboard = keyboard_default_with_start)


def get_events(event):
	global keyboard_default_with_start
	#print(event)
	message = event.object.message

	peer_id = message['peer_id']
	text = message['text']
	id_ = message['id']

	if peer_id in settings['vk_bot']['admins']:

		d = create_d(peer_id, '')
		d_command = message_command(peer_id, text)
		if d_command != None:
			return d_command

		if check_compliance(text, settings['options']['commands']['change_profile']):
			chat_history(peer_id, id_, 'change_profile')
			d['text'] = 'Выберите новый профиль'
			d['keyboard'] = keyboard_profiles

		elif peer_id in d_id and d_id[peer_id]['d'] == 'change_profile':
			for sh in sheet_names:
				if text == sh:
					settings['options']['profile'] = text
					WRITE('settings.json', settings).write_json()
					d_id[peer_id]['d'] = {}
					d['text'] = 'Установлен новый профиль - ' + text
					keyboard_default_with_start = create_keyboard('callback', [[k_start], [text, k_change]])
					d['keyboard'] = keyboard_default_with_start
					return d
			d['text'] = 'Неверный профиль' 
			d['keyboard'] = keyboard_profiles

		elif check_compliance(text, settings['options']['commands']['confirm']):
			d = d_id[peer_id]['d']
			profile_settings = settings['options']['profile']
			spam_ids = user_ids[profile_settings]['id']
			print('spam_ids')
			print(spam_ids)
			#d['peer_id'] = spam_ids #  МЕНЯЕТ ТЕКУЩИЙ iD НА СПИСОК iD МОИХ ОДНОГРУППНИКОВ
			d['keyboard']['buttons'] = []
			chat_history(peer_id, id_, 'start_spamming')

		elif check_compliance(text, settings['options']['commands']['start']):
			if 'reply_message' in message:
				id_ = message['reply_message']['id']
			elif message['fwd_messages'] == []:
				if peer_id not in d_id:
					chat_history(peer_id, id_, {})
				id_ = d_id[peer_id]['id']

			message = vk.messages.getById(message_ids = id_)['items'][0]
			message = reply(message)

			if not message:
				chat_history(peer_id, 0, {})
				d['text'] = 'Вы переслали несколько сообщений!'
				d['keyboard'] = keyboard_default_with_start

			d = get_attachments(peer_id, message)
			if check_compliance(d['text'], settings['options']['commands']['start']):
				d['text'] = ''

			d['keyboard'] = {'buttons': [[{'action': {'label': 'Confirm',
                                       'type': 'callback'}}]],
              				'one_time': False}

            # keyboard_confirm #create_keyboard('callback', [[settings['options']['commands']['confirm']]])

			chat_history(peer_id, id_, d)

			return d

		#elif check_compliance(text, 'Get chats'): # получить список всех бесед

		else:
			d['text'] = 'Нажмите ' + settings['options']['commands']['start'] + ', чтобы обработать составленное сообщение, а потом ' + settings['options']['commands']['confirm'] + ', чтобы начать рассылку'
			d['keyboard'] = keyboard_default_with_start
			chat_history(peer_id, id_, {})
			
		return d


vk, longpoll = auth(settings['vk_bot']['token'], settings['vk_bot']['group_id'])



#WRITE('settings.json', settings).write_json()


d_id = {}
run = True
exceptions = (requests.exceptions.ConnectionError, vk_api.exceptions.ApiError, KeyError)
user_ids = READ('user_ids' + settings['options']['file_ext']).read() # словарь со списком всех id (key - user_ids) и ключами-именами
#print('user_ids')
#print(user_ids)
#pprint(user_ids[settings['options']['profile']]['id'])



# СОЗДАЁМ КЛАВИАТУРЫ
#_______________________________________________________________________________________________________________
k_start = settings['options']['commands']['start']
k_profile = settings['options']['profile']
k_change = settings['options']['commands']['change_profile']
sheet_names = user_ids['sheet_names']
sheet_names_for_keyboard = create_rows_in_mas(sheet_names)

keyboard_default_with_start = create_keyboard('callback', [[k_start], [k_profile, k_change]])
keyboard_profiles = create_keyboard('callback', sheet_names_for_keyboard)
keyboard_confirm = create_keyboard('callback', [[settings['options']['commands']['confirm']]])


# стартовое сообщение
vk.messages.send(peer_ids = settings['vk_bot']['admins'],
				 message = 'Бот готов к работе (^-^)',
				 keyboard = str(json.dumps(keyboard_default_with_start, ensure_ascii=False).encode('utf-8').decode('utf-8')),  
				 random_id = vk_api.utils.get_random_id())


def __main__():
	for event in longpoll.listen():
	    if event.type == VkBotEventType.MESSAGE_NEW:
	    	t = time.time()

	    	d = get_events(event)
	    	pprint(d)
	    	if not d or d == None:
	    		continue

	    	print('время обработки ивента')
	    	print(time.time() - t)

	    	vk.messages.send(peer_ids = d['peer_id'],
							 message = d['text'],
							 attachment = d['attachments'], 
							 lat = d['lat'], 
							 long = d['long'], 
							 sticker_id = d['sticker_id'], 
							 keyboard = str(json.dumps(d['keyboard'], ensure_ascii=False).encode('utf-8').decode('utf-8')),  
							 random_id = vk_api.utils.get_random_id())


	    	if d_id[d['spare_peer_id']]['d'] == 'start_spamming':
	    		message_time = 'Время рассылки составило ' + str(round(time.time() - t, 2)) + ' c'
	    		keyboard_start = str(json.dumps(keyboard_default_with_start, ensure_ascii=False).encode('utf-8').decode('utf-8'))
	    		vk.messages.send(peer_ids = d['spare_peer_id'], 
	    						 message = message_time, 
	    						 keyboard = keyboard_start, 
	    						 random_id = vk_api.utils.get_random_id())

	    		d_id[d['spare_peer_id']]['d'] = {}

	    	print('общее время')
	    	print(time.time() - t)


while run:
	try:
		if __main__() == __main__():
			__main__()
	except exceptions as e:
		print(e)
		time.sleep(settings['vk_bot']['time_sleep_exceptions'])
		run = True


'''



'''