# -*- coding: utf-8 -*-
"""CoronaVirus Tweets Analytics

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/16IZOLyBF1SxldGVeqvLIPYVjyW4miyn7

# **Corona Virus-related Tweeets Analytics**

This notebook is dedicated to loading and analizing the data in CoronaVirus tweets dataset maintained in IEEE (see the links below).

In order to run this notebook, you should complete the pre-requisites below

- in your Google Drive, create a folder 'CoronaTweets'

**Note**: The IEEE-backed tweets data stored in corona_tweets bucket in GCP
"""

!pip install pdpipe pydata-google-auth wordcloud

import pandas as pd
import pdpipe as pdp
import datetime as dt
import sqlite3
import pydata_google_auth

from google.colab import drive
from google.colab import auth

import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
from wordcloud import WordCloud

import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem.snowball import SnowballStemmer

nltk.download('stopwords')
nltk.download('punkt')

stemmer = SnowballStemmer('english')
stop_words = stopwords.words('english')

# problem-specific tokens to exclude
filter_out_from_tweets = [
    'rt',
    'http',
    'https',
    'corona',
    'coronavirus',
    'virus',
    'covid',
    'sars'
]

def drop_tweeet_user_name(tweet_text):
  tweet = re.sub('@[^\s]+','', tweet_text)
  return tweet


def clean_text(original_string):
  return re.sub(r'[^a-zA-Z ]', '', original_string)

def wordfilter(original_string):
    filtered = []
    to_eliminate = stop_words + filter_out_from_tweets
    tokens = word_tokenize(original_string)
    for word in tokens:
      if word not in to_eliminate:
        filtered.append(stemmer.stem(word))
    
    result = " ".join(filtered)
    return result


def is_positive(sentiment_score):
    if sentiment_score > 0:
        return 1
    else:
        return 0


def is_negative(sentiment_score):
    if sentiment_score < 0:
        return 1
    else:
        return 0


def is_neutral(sentiment_score):
    if sentiment_score == 0:
        return 1
    else:
        return 0

# This will mount the drive to this notebook
drive.mount('/content/drive')

# This will connect to your project and list all buckets 
auth.authenticate_user()
project_id = 'fcg-bi-prod'
!gcloud config set project {project_id}
!gsutil ls

# this will copy data from the bucket with corona tweets to 
# the personal Google drive ('My Drive/CoronaTweets/' subfolder, namely)
#
# Note: !gsutil -m cp -r gs://{bucket_name}/* /content/drive/My\ Drive/CoronaTweets/
#       runs faster (vs. the command without -m switch) 
#       but the process halts for some time for a weird reason 
#       (as some threads do not return its completion state timely?) - 
#       so you should be patient to wait for it to complete correctly
bucket_name = 'corona_tweets'
!gsutil -m cp -r gs://{bucket_name}/* /content/drive/My\ Drive/CoronaTweets/

base_db_folder = '/content/drive/My Drive/CoronaTweets'
tweet_db_paths = [
    # incomplete data - '/corona_tweets_1M.db/corona_tweets_1M.db',   # 27.02.2020 10:36 01.03.2020 18:24 1578957
    # malformed - '/corona_tweets_2M_2/corona_tweets_2M_2.db',  # 02.03.2020 17:27	07.03.2020 4:57	2268665
    '/corona_tweets_3M/tweets.db',  # 07.03.2020 5:06	14.03.2020 4:46	7472368
    '/corona_tweets_1M/tweets.db',  # 14.03.2020 5:23	15.03.2020 3:16	1903768
    '/corona_tweets_2M_3/tweets.db',  # 15.03.2020 3:28	16.03.2020 4:31	2081576
    '/corona_tweets_1M_2/tweets.db',  # 16.03.2020 4:38	17.03.2020 3:08	1889781
    '/corona_tweets_2L/tweets.db'  # 17.03.2020 3:12	17.03.2020 6:10	280304
]

pipeline = pdp.PdPipeline([
    pdp.ColRename({'unix': 'tweet_date'}),
    pdp.ApplyByCols('sentiment', is_positive, 'is_positive', drop=False),
    pdp.ApplyByCols('sentiment', is_negative, 'is_negative', drop=False),
    pdp.ApplyByCols('sentiment', is_neutral, 'is_neutral', drop=False),
])

tweets_df = pd.DataFrame()

for tweets_db in tweet_db_paths:
    full_tweet_db_path = base_db_folder + tweets_db
    print(dt.datetime.now(), "Processing started: ", full_tweet_db_path)
    conn = sqlite3.connect(full_tweet_db_path)
    c = conn.cursor()
    df_pie = pd.read_sql("SELECT * FROM sentiment", conn)
    df_pie['unix'] = pd.to_datetime(df_pie['unix'], unit='ms').dt.date  # cast to date
    df = pipeline.apply(df_pie).sort_values(by=['tweet_date'])

    if df.shape[0] < 1:
        tweets_df = df
    else:
        # concatenate
        frames = [tweets_df, df]
        tweets_df = pd.concat(frames)

    print(":: Processed fully: ", full_tweet_db_path)

# aggregate the summary statistics
df_positives = tweets_df.groupby(['tweet_date'])['is_positive'].sum().reset_index()
df_negatives = tweets_df.groupby(['tweet_date'])['is_negative'].sum().reset_index()
df_neutrals = tweets_df.groupby(['tweet_date'])['is_neutral'].sum().reset_index()

tweets_summary_df = pd.merge(
    pd.merge(df_positives, df_negatives, on=['tweet_date']),
    df_neutrals, on=['tweet_date'])

print('---- Tweet summary info: ----')
print(tweets_summary_df.info())
print('---- Head: ----')
print(tweets_summary_df.head())
print('---- Tail: ----')
print(tweets_summary_df.tail())

# WRITE TO BQ

# tweets_summary_df.to_gbq('covid19_tracking.covid19_tweets', project_id='fcg-bi-prod', if_exists='replace')

# pulling the stats from WHO / JHO Univ on COVID-19 (confirmed cases, deaths, recovered cases)

# fetching the latest time series data sets
confirmed_ts_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv")
deaths_ts_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_global.csv")
recovered_ts_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_recovered_global.csv")

confirmed_ts_melted_df = confirmed_ts_df.melt(id_vars=['Province/State', 'Country/Region', 'Lat', 'Long',],
                     var_name='covid_date', value_name='confirmed').copy()

deaths_ts_melted_df = deaths_ts_df.melt(id_vars=['Province/State', 'Country/Region', 'Lat', 'Long',],
                     var_name='covid_date', value_name='deaths').copy()

recovered_ts_melted_df = recovered_ts_df.melt(id_vars=['Province/State', 'Country/Region', 'Lat', 'Long',],
                     var_name='covid_date', value_name='recovered').copy()

pipeline = pdp.PdPipeline([
    pdp.ApplyByCols(['covid_date'], pd.to_datetime),
    pdp.ColRename({'Country/Region': 'country_id', 'Province/State': 'state', 'Lat': 'lat', 'Long': 'long'})

])

confirmed_ts_fcg_df = pipeline.apply(confirmed_ts_melted_df).sort_values(by=['country_id', 'covid_date'])
deaths_ts_fcg_df = pipeline.apply(deaths_ts_melted_df).sort_values(by=['country_id', 'covid_date'])
recovered_ts_fcg_df = pipeline.apply(recovered_ts_melted_df).sort_values(by=['country_id', 'covid_date'])

covid_df = pd.merge(
    pd.merge(confirmed_ts_fcg_df, deaths_ts_fcg_df, on=['state', 'country_id', 'lat', 'long','covid_date']),
    recovered_ts_fcg_df, on=['state', 'country_id', 'lat', 'long','covid_date'])

covid_df.head()

# get summary COVID-19 statistics across the globe (we need on the global scale, to match with the tweet stat numerals)

df_confirmed = covid_df.groupby(['covid_date'])['confirmed'].sum().reset_index()
df_deaths = covid_df.groupby(['covid_date'])['deaths'].sum().reset_index()
df_recovered = covid_df.groupby(['covid_date'])['recovered'].sum().reset_index()

covid_summary_df = pd.merge(
    pd.merge(df_confirmed, df_deaths, on=['covid_date']),
    df_recovered, on=['covid_date'])

# merge the COVID-19 core metrics and CoronaVirus Tweet Charts
dates_with_tweet_stats = [
      '2020-03-07',
      '2020-03-08',
      '2020-03-09', 
      '2020-03-10', 
      '2020-03-11',  
      '2020-03-12',
      '2020-03-13', 
      '2020-03-14',
      '2020-03-15',
      '2020-03-16',
      # '2020-03-17'   
]


pipeline = pdp.PdPipeline([
    pdp.ApplyByCols(['covid_date'], pd.to_datetime),
    pdp.ColRename({'covid_date': 'tweet_date'}),
    pdp.ValKeep(dates_with_tweet_stats, columns=['tweet_date']),
])

covid_summary_df = pipeline.apply(covid_summary_df).sort_values(by=['tweet_date'])

covid_summary_df['tweet_date'] = pd.to_datetime(covid_summary_df['tweet_date']).dt.date

covid_summary_df = pd.merge(covid_summary_df, tweets_summary_df, on=['tweet_date'])

covid_summary_df.head()

px.line(covid_summary_df, x='tweet_date', y='is_positive', title='Positive tweets on COVID-19: Global Evolution')

px.line(covid_summary_df, x='tweet_date', y='is_negative', title='Negative tweets on COVID-19: Global Evolution')

px.line(covid_summary_df, x='tweet_date', y='is_neutral', title='Neutral tweets on COVID-19: Global Evolution')

# History of CoronaVirus-related tweets globally: Create traces
fig = go.Figure()
fig.add_trace(go.Scatter(x=covid_summary_df['tweet_date'], y=covid_summary_df['is_neutral'],
                    mode='lines+markers',
                    name='Neutral'))
fig.add_trace(go.Scatter(x=covid_summary_df['tweet_date'], y=covid_summary_df['is_positive'],
                    mode='lines+markers',
                    name='Positive'))
fig.add_trace(go.Scatter(x=covid_summary_df['tweet_date'], y=covid_summary_df['is_negative'],
                    mode='lines+markers', 
                    name='Negative'))
# Edit the layout
fig.update_layout(title='History of CoronaVirus-related tweets globally (Mar 7-16, 2020)',
                   xaxis_title='Date',
                   yaxis_title='Number of tweets')
fig.show()

# additional ratio features
pipe_calc = pdp.PdPipeline([
    pdp.ApplyToRows(lambda row: (row['deaths']/row['confirmed']), 'dead_to_confirmed'),
    pdp.ApplyToRows(lambda row: (row['recovered']/row['confirmed']), 'recovered_to_confirmed'),
    pdp.ApplyToRows(lambda row: (row['is_positive']/(row['is_positive'] + row['is_negative'] + row['is_neutral'])), 'pos_ratio'),
    pdp.ApplyToRows(lambda row: (row['is_negative']/(row['is_positive'] + row['is_negative'] + row['is_neutral'])), 'neg_ratio'),
    pdp.ApplyToRows(lambda row: (row['is_neutral']/(row['is_positive'] + row['is_negative'] + row['is_neutral'])), 'neu_ratio'),                  
])

# calculate ratio attributes
covid_summary_df = pipe_calc.apply(covid_summary_df)
display(covid_summary_df)

"""## Dead-to-Confirmed Cases Ratio vs. Positive Tweets Ratio"""

# Plot using Seaborn
ax = sns.lmplot(x='dead_to_confirmed', y='pos_ratio', data=covid_summary_df,
           fit_reg=True)
ax

"""As we can see, it looks like there is no any strong relation between the ratio of the positive tweets toward Corona and the actual cumulative dead-to-confirmed ratio.

## Dead-to-Confirmed Cases Ratio vs. Positive Tweets Ratio
"""

ax = sns.lmplot(x='dead_to_confirmed', y='neg_ratio', data=covid_summary_df,
           fit_reg=True)
ax

"""As we can see, there might be a mediumm-to-strong relation between the ratio of the negative tweets toward Corona and the actual cumulative dead-to-confirmed ratio.

# Positive vs. Negative Tweets Ratio
"""

ax = sns.lmplot(x='pos_ratio', y='neg_ratio', data=covid_summary_df,
           fit_reg=True)
ax

# Negative tweets: negative tweets, Mar 16, 2020

pipeline = pdp.PdPipeline([
    pdp.ValKeep([1], columns=['is_negative']),
    pdp.ValKeep([dt.date(2020,3,16)], columns=['tweet_date']),
])

neg_tweets_df = pipeline.apply(tweets_df).sort_values(by=['tweet_date'])
# neg_tweets_df = neg_tweets_df[neg_tweets_df['tweet_date'] == dt.date(2020,3,16) ]  
neg_tweets_df.head()

"""## WordCloud: Negative Tweets, Mar 16, 2020"""

# Word cloud: negative tweets, Mar 16, 2020

# convert cleaned tweet texts to lower case
neg_tweets_df['tweet'] = neg_tweets_df['tweet'].str.lower()

pipeline = pdp.PdPipeline([
    pdp.ColDrop(['sentiment',	'is_neutral',	'is_negative',	'is_positive']),
    pdp.ApplyByCols('tweet', drop_tweeet_user_name),
    pdp.ApplyByCols('tweet', clean_text),
    pdp.ApplyByCols('tweet', wordfilter)
])

neg_tweets_df = pipeline.apply(neg_tweets_df)

text_base = ' '.join(neg_tweets_df['tweet'].tolist())
wordcloud = WordCloud().generate(text_base)
plt.imshow(wordcloud)
plt.axis("off")

plt.show()

# Positive tweets: Mar 16, 2020

pipeline = pdp.PdPipeline([
    pdp.ValKeep([1], columns=['is_positive']),
    pdp.ValKeep([dt.date(2020,3,16)], columns=['tweet_date'])
])

pos_tweets_df = pipeline.apply(tweets_df).sort_values(by=['tweet_date'])
# pos_tweets_df = pos_tweets_df[pos_tweets_df['tweet_date'] == dt.date(2020,3,16) ]  
pos_tweets_df.head()

"""## WordCloud: Positive Tweets, Mar 16, 2020"""

# Word cloud: positive tweets, Mar 16, 2020

# convert cleaned tweet texts to lower case
pos_tweets_df['tweet'] = pos_tweets_df['tweet'].str.lower()

pipeline = pdp.PdPipeline([
    pdp.ColDrop(['sentiment',	'is_neutral',	'is_negative',	'is_positive']),
    pdp.ApplyByCols('tweet', drop_tweeet_user_name),
    pdp.ApplyByCols('tweet', clean_text),
    pdp.ApplyByCols('tweet', wordfilter)
])

pos_tweets_df = pipeline.apply(pos_tweets_df)

text_base = ' '.join(pos_tweets_df['tweet'].tolist())
wordcloud = WordCloud().generate(text_base)
plt.imshow(wordcloud)
plt.axis("off")

plt.show()

"""## WordCloud: Negative Tweets, Mar 15, 2020"""

# Negative tweets: negative tweets, Mar 15, 2020

pipeline = pdp.PdPipeline([
    pdp.ValKeep([1], columns=['is_negative']),
    pdp.ValKeep([dt.date(2020,3,15)], columns=['tweet_date']),
])

neg_tweets_df = pipeline.apply(tweets_df).sort_values(by=['tweet_date']) 
neg_tweets_df.head()

# Word cloud: negative tweets, Mar 15, 2020

# convert cleaned tweet texts to lower case
neg_tweets_df['tweet'] = neg_tweets_df['tweet'].str.lower()

pipeline = pdp.PdPipeline([
    pdp.ColDrop(['sentiment',	'is_neutral',	'is_negative',	'is_positive']),
    pdp.ApplyByCols('tweet', drop_tweeet_user_name),
    pdp.ApplyByCols('tweet', clean_text),
    pdp.ApplyByCols('tweet', wordfilter)
])

neg_tweets_df = pipeline.apply(neg_tweets_df)

text_base = ' '.join(neg_tweets_df['tweet'].tolist())
wordcloud = WordCloud().generate(text_base)
plt.imshow(wordcloud)
plt.axis("off")

plt.show()

"""## WordCloud: Positive Tweets, Mar 15, 2020"""

# Positive tweets: Mar 15, 2020

pipeline = pdp.PdPipeline([
    pdp.ValKeep([1], columns=['is_positive']),
    pdp.ValKeep([dt.date(2020,3,15)], columns=['tweet_date'])
])

pos_tweets_df = pipeline.apply(tweets_df).sort_values(by=['tweet_date']) 
pos_tweets_df.head()

# Word cloud: positive tweets, Mar 15, 2020

# convert cleaned tweet texts to lower case
pos_tweets_df['tweet'] = pos_tweets_df['tweet'].str.lower()

pipeline = pdp.PdPipeline([
    pdp.ColDrop(['sentiment',	'is_neutral',	'is_negative',	'is_positive']),
    pdp.ApplyByCols('tweet', drop_tweeet_user_name),
    pdp.ApplyByCols('tweet', clean_text),
    pdp.ApplyByCols('tweet', wordfilter)
])

pos_tweets_df = pipeline.apply(pos_tweets_df)

text_base = ' '.join(pos_tweets_df['tweet'].tolist())
wordcloud = WordCloud().generate(text_base)
plt.imshow(wordcloud)
plt.axis("off")

plt.show()

"""# References

- Build pipelines with Pandas using “pdpipe” (https://towardsdatascience.com/https-medium-com-tirthajyoti-build-pipelines-with-pandas-using-pdpipe-cade6128cd31)
- Transferring data between Google Drive and Google Cloud Storage using Google Colab (https://medium.com/@philipplies/transferring-data-from-google-drive-to-google-cloud-storage-using-google-colab-96e088a8c041)
- CoronaVirus Tweets DataSet Home (https://ieee-dataport.org/open-access/corona-virus-covid-19-tweets-dataset) - it had been shared under GNU license; however, as of Mar 20, 2020 morning CET, the public access to this dataset has been closed by the dataset mainteiner ( by Rabindra Lamsal at Database Systems and Artificial Intelligence Lab)
- https://sentiment.live/ - the live feed that produces the dataset above
"""