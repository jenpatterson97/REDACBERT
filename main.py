# -*- coding: utf-8 -*-
"""attnheads_censor.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1vc0pXHKnX1DCQMsjP1O0bpIfYB6NPNhp
"""

# Commented out IPython magic to ensure Python compatibility.
! git clone https://github.com/huggingface/transformers
# %cd transformers
! pip install .
! pip install -r ./examples/requirements.txt

! pip install captum
import os
import sys

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

import torch
import torch.nn as nn

from transformers import BertTokenizer, BertForQuestionAnswering, BertConfig
from captum.attr import visualization as viz
from captum.attr import IntegratedGradients, LayerConductance, LayerIntegratedGradients
from captum.attr import configure_interpretable_embedding_layer, remove_interpretable_embedding_layer

#QA
from transformers import BertTokenizer, BertForQuestionAnswering
import torch

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
modelqa = BertForQuestionAnswering.from_pretrained('bert-large-uncased-whole-word-masking-finetuned-squad', output_hidden_states= True)

def infer(input_ids):
  token_type_ids = [0 if i <= input_ids.index(102) else 1 for i in range(len(input_ids))]
  start_scores, end_scores, hiddens = modelqa(torch.tensor([input_ids]), token_type_ids=torch.tensor([token_type_ids]))

  all_tokens = tokenizer.convert_ids_to_tokens(input_ids)
  start = torch.argmax(start_scores)
  end = torch.argmax(end_scores)+1
  
  answer = ' '.join(all_tokens[torch.argmax(start_scores) : torch.argmax(end_scores)+1])
  context = ' '.join(all_tokens[torch.argmax(start_scores)-5 : torch.argmax(end_scores)+5])
  
  return answer, all_tokens, start.numpy(),end.numpy(), hiddens, context

from sklearn.metrics.pairwise import cosine_similarity

def cos_sim(tok1s,race):

  _, _, _, _, hiddensr, _ = infer(race)

  _, _, _, _, hiddenst, _ = infer(tok1s)
  v = -23

  r = []
  for i in hiddensr[v:-1]:
    r.append(i.detach().numpy()[0])
  r = np.array(r).sum(axis =(0,1)).reshape(1,-1)

  t = []
  for i in hiddenst[v:-1]:
    t.append(i.detach().numpy()[0])

  t = np.array(t).sum(axis =(0,1)).reshape(1,-1)
  return(cosine_similarity(r,t).mean())

#cosine similarity of word to be redacted with race
def embed_sim(all_tokens, start,end, thresh):
  racisms = []
  for w in ['race','black','hispanic','white','asian','arab']:
    race = tokenizer.encode(w)
    ans = tokenizer.encode(tokenizer.convert_tokens_to_string(all_tokens[start-1:end+1])) #add some context to it
    racisms.append(cos_sim(ans,race))
  print(np.array(racisms))
  return np.array(racisms).mean()> thresh

text = ' Of the plaintiff in consideration of several different factors, namely that the defendent, with respect to their race, has considered it upon the jury of utmost precedence, that these factors be taken into account when delivering the judgement. Rather than race to conclusions, the jury has taken its sweet time, against the wishes of the plaintiff. It has been found, considering the origin of the aforementioned to be white, that they cannot be found in violation of the law.'
question ="what is the race of the defendent?"

def delete_racism(question,text,thresh):
  q_text = question+' ' + text
  input_ids = tokenizer.encode(question,text)
  answer, all_tokens, start,end, hiddens, context = infer(input_ids)
  while ('red ##aa ##cted' not in answer) and start < end and embed_sim(all_tokens, start,end, thresh) and '[SEP]' not in answer and '[CLS]' not in answer:
    print('Question:',q_text)
    print('Answer: ',tokenizer.decode(tokenizer.convert_tokens_to_ids(answer), skip_special_tokens = True))
    
    #replace tokens from start-end with redacted
    if '##' in tokenizer.clean_up_tokenization(answer):
      end = start+1
    j = start
    for i in range(start,end):
      red = tokenizer.convert_ids_to_tokens(tokenizer.encode('REDAACTED'))

      all_tokens[j:j] = red
      j = len(red)+j
      all_tokens.pop(j)

    q_text = tokenizer.decode(tokenizer.convert_tokens_to_ids(all_tokens), skip_special_tokens = True)
    input_ids = tokenizer.encode(q_text)
    answer, all_tokens, start,end, hiddens, context = infer(input_ids)
    print('NEXT LOOP')

  return q_text

def help_eval(text, threshold):
  question ="what is their race?"
  tokens = tokenizer.encode(text)
  all_predicted_answers = []

  chunksize = 460
  tot_text = ''
  eval_list = []
  for i in range(0, len(tokens), chunksize):
    chunk = tokens[i:i+chunksize]
    question, text = question, tokenizer.decode(chunk, skip_special_tokens=True)
    input_ids = tokenizer.encode(question,text)
    non_racist = delete_racism(question,text, threshold).split(question)[1]
    eval_str_1 = non_racist.split(' ')[1:]
    tot_text += non_racist
    eval_list.extend(eval_str_1)
  return eval_list

def evaluate(text,correct,threshold):
  TP = 0
  FP = 0
  TN = 0
  FN = 0

  ans = help_eval(text, threshold)
  base = text.split(' ')
  correct = correct.split(' ')
  print(ans)
  if len(base)!= len(ans) or len(correct)!= len(ans):
    ans = ans[0]
    print('ERROR lengths not equal, metrics wont work!')
    print(len(ans))
    print(len(base))
    print(len(correct))
    print(ans)
    return (ans,base,correct)
  # print(ans)
  # print(base)
  # print()
  for i in range(len(ans)):
    if 'redaacted' in ans[i] and 'redaacted' in correct[i]:
      TP+=1
    if 'redaacted' in ans[i] and 'redaacted' not in correct[i]:
      FP+=1
    if 'redaacted' not in ans[i] and 'redaacted' in correct[i]:
      FN+=1
    if 'redaacted' not in ans[i] and 'redaacted' not in correct[i]:
      TN+=1
  return {'TP': TP,'FP': FP,'TN': TN,'FN': FN}

# # ######### This is the only part you have to change, the ex_str is the thing to be unracismed, the ex_cor is the one labeled with redacted

# ex_str = 'Indian is his race. Brown is the answer. hello this is string. The belgian company is good. The owner is born in India. hello this is string. hello this is string. hello this is string. hello this is string. He is nice.'
# ex_cor = 'redaacted is his race. redaacted is the answer. hello this is string. The belgian company is good. The owner is born in redaacted. hello this is string. hello this is string. hello this is string. hello this is string. He is nice.'
# #for i in [0.0001, .1,.2,.3,0.4,0.5,0.6,.7.75,.8,.83,.85,.87,.9,.92,.95,0.999]:

# evaluate(ex_str,ex_cor,0.6)

with open('/content/100 Paragraphs.txt') as f:
   text = f.read()

texts = text.split('SPLIT')
for i,t in enumerate(texts):
  texts[i] = t.split(' ')

import pandas as pd
pd.DataFrame(texts).to_csv('/content/test.csv')


'On December 4, 1982, defendant visited his friend Gary Newell at the latters home in Seattle, Washington. Defendant arrived in a rental car and, soon thereafter, returned to the car and retrieved an army jacket that was either Silveiras or very similar to it. Both Newell and his housemate, Leonard Brouette, recalled that the name on the jacket began with S and was a Hispanic sounding name. The next morning, defendant said he was leaving for the airport and Grand Rapids, Michigan.'




# texts

import matplotlib.pyplot as plt

ps = []
rs = []
thr_i = []

for thrr in [0.87,0.875,0.88,0.885]:
  df = pd.read_csv('/content/test.csv', header = None)
  results = []
  print(len(df))
  for i in range(0, len(df), 2):
    ex_str_list = list(df.iloc[i].dropna())
    redac_list = list(df.iloc[i+1].dropna())
    ##form
    ex_cor_list = []

    for i in range(len(ex_str_list)):
      val = ex_str_list[i]
      if redac_list[i] == '1':
        print('redac!')
        val = 'redaacted'
      ex_cor_list.append(val)

    ex_str = ' '.join(ex_str_list,)
    ex_cor = ' '.join(ex_cor_list)
    result = evaluate(ex_str,ex_cor,thrr)
    print(result)
    results.append(result)

  result_irl = []
  for val in results:
    if type(val)==dict:
      result_irl.append(val)
  print(len(result_irl))

  thr_i.append(thrr)
  precs = []
  recs = []
  
  for d in result_irl:
    try:
      Precision = d['TP'] / (d['TP'] + d['FP'])
      Recall = d['TP'] / (d['TP'] + d['FN'])
      precs.append(Precision)
      recs.append(Recall)
    except:
      pass

  ps.append(np.array(precs).mean())
  rs.append(np.array(recs).mean())
  print('___________DONE WITH THRESHOLD: ',thrr,'_________________')
plt.scatter(ps, rs)

for val in ps:
  print(val)

rs

F = []
for i in range(len(ps)):
  try:
    F.append((2 * ps[i] * rs[i]) / (ps[i] + rs[i]))
  except:
    F.append(0)
F
plt.scatter(thr_i[:-2], F[:-2], c = thr_i[0:-2])
plt.plot(thr_i[:-2], F[:-2])
plt.xlabel('Threshold (Lambda)')
plt.xlim((0,1))
plt.cool()
plt.ylabel('F-Score')

plt.scatter(ps,rs, alpha = 0.7, c = thr_i)
plt.plot(ps,rs)
plt.xlabel('Precision')
plt.ylabel('Recall')
# plt.xlim((0,1))
# plt.ylim((0,1))

