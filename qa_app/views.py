from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import JsonResponse
from django import forms
from django.urls import reverse
from django.utils import timezone

from .models import ChatHistory

from langchain.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA, ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory , ChatMessageHistory 
from langchain.schema import Document

import pandas as pd
import os
import sqlite3
from datetime import datetime
from django.shortcuts import render
from pytz import timezone
from django.contrib import messages

# Create your views here.



# 전역변수
i = 0

# Chroma 데이터베이스 초기화 - 사전에 database가 완성 되어 있다는 가정하에 진행 - aivleschool_qa.csv 내용이 저장된 상태임
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
database = Chroma(persist_directory="./database", embedding_function=embeddings)


# 채팅

def chatting(request):
    if not request.user.is_authenticated:        
        return JsonResponse({'error': '로그인이 필요한 페이지입니다.', 'login_required': True}, status=403)
    global i
    
    if request.method == 'GET':
        # 세션의 대화 내역 초기화
        request.session['conversation'] = []
        request.session.save()
        
    conversation = request.session.get('conversation', [])
    memory = ConversationBufferMemory(memory_key="chat_history", input_key="question", output_key="answer", return_messages=True)
    
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    database = Chroma(persist_directory="./database", embedding_function=embeddings)
    if request.method == 'POST':
        query = request.POST.get('question')
        
        seoul_time = datetime.now(timezone('Asia/Seoul')).strftime('%H:%M')

        conversation.append({'user': query, 'timestamp': seoul_time})

        chat = ChatOpenAI(model="gpt-3.5-turbo")
        
        k = 3
        retriever = database.as_retriever(search_kwargs={"k": k})
        qa = ConversationalRetrievalChain.from_llm(llm=chat, retriever=retriever, memory=memory, return_source_documents=True, output_key="answer")
        result = qa({"question": query})

        conversation.append({'bot': result['answer'], 'timestamp': seoul_time})

        request.session['conversation'] = conversation
        request.session.save()

        # SQLite 데이터베이스 초기화
        path = './db_chatlog/chatlog.db'
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY,
            datetime TEXT NOT NULL,
            query TEXT NOT NULL,
            sim1 REAL NOT NULL,
            sim2 REAL NOT NULL,
            sim3 REAL NOT NULL,
            answer TEXT NOT NULL)
        ''')
        conn.commit()
        conn.close()
        
        dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        score = []
        result2 = database.similarity_search_with_score(query, k=k)
        for doc in result2:
            score.append(round(doc[1], 5))
        #혹시나 유사도가 안나오면 0으로 처리    
        while len(score) < k:
            score.append(0.0)
             
        conn = sqlite3.connect(path)
        history_data = pd.DataFrame({'datetime': [dt], 'query': [query], 'sim1': [score[0]], 'sim2': [score[1]], 'sim3': [score[2]], 'answer': [result['answer']]})
        history_data.to_sql('history', conn, if_exists='append', index=False)
        
        d2 = pd.read_sql('SELECT * FROM history', conn)
        
        d2.to_csv("answer.csv", index=False)
        
        conn.close()

        # admin 페이지에 기록 남기기
        chat_history_entry = ChatHistory(
            datetime=dt,
            query=query,
            sim1=score[0],
            sim2=score[1],
            sim3=score[2],
            answer=result['answer']
        )
        chat_history_entry.save()
        
        # 벡터 DB 구현 도전
        df = pd.read_csv('answer.csv', encoding='utf-8')
        df['answer'] = df.apply(lambda row: str(row['query']) + ", " + row['answer'], axis=1)
        i = i + 1
        text_list = df.loc[df['id']==i]['answer'].to_list()
        metadata_list = df.loc[df['id']==i]['query'].to_list()
        metadata = [{'질문': category} for category in metadata_list]
        documents = [Document(page_content=text, metadata=meta) for text, meta in zip(text_list, metadata)]
        

        database.add_documents(documents)
        
    return render(request, 'qa/chat.html', {'conversation': conversation})

# 대화 내용 초기화
@login_required
def reset(request):
    global i
    
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    database = Chroma(persist_directory="./database", embedding_function=embeddings)
    
    # 세션의 대화 내역을 초기화
    request.session['conversation'] = []
    request.session['chat_history'] = []
    
    # admin에서 기록 초기화
    ChatHistory.objects.all().delete()
    
    # SQLite 데이터베이스 초기화
    path = './db_chatlog/chatlog.db'
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute('''DROP TABLE IF EXISTS history''')
    conn.commit()
    conn.close()
    #Chroma 데이터베이스에서 메타데이터가 '질문'인 문서 삭제
    
    db = database.get()
    delete_db = pd.DataFrame(db)
    delete_list = delete_db[delete_db['metadatas'].apply(lambda x: '질문' in x)]['ids'].to_list()
    delete_list
    
    for i in delete_list:
        database.delete(ids=i
    )
    i = 0
    return redirect('qa:chatting')