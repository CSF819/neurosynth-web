import cPickle
from nsweb.models.studies import Studies
from nsweb.models.features import Features

# Re-initialize database
def init_database(db):
    db.drop_all()
    db.create_all()

# Read in the study data (contains pickled data originally in the database.txt file)
def read_pickle_database(data_dir, pickle_database):
    pickle_data = open( data_dir + pickle_database,'rb')
    dataset = cPickle.load(pickle_data)
    pickle_data.close()
    return dataset

# Reads features into memory. returns a list of features and a dictionary of those features with pmid as a key
def read_features_text(data_dir, feature_database):
    features_text=open(data_dir + feature_database)
    feature_list = features_text.readline().split()[1:] # List of feature names
    
    feature_data = {} # Store mapping of studies --> features, where key is pmid and values are frequencies
    for x in features_text:
        x=x.split()
        feature_data[int(x[0])] = map(float,x[1:])
    features_text.close()
    return (feature_list,feature_data)

#commits features to database
def add_features(db, feature_list):
        features=Features(db)
        feature_dict={}

        for x in feature_list:
            feature_dict[x] = features.Feature(feature=x)
            db.session.add(feature_dict[x])
            db.session.commit()
        return feature_dict


def add_studies(db, dataset, feature_list, feature_data, feature_dict):
    # Create Study records
    studies = Studies(db)
    for i,x in enumerate(dataset):
        study = studies.Study(
                              pmid=int(x.get('id')),
                              doi=x.get('doi'),
                              title=x.get('title'),
                              journal=x.get('journal'),
                              space=x.get('space'),
                              authors=x.get('authors'),
                              year=x.get('year'),
                              table_num=x.get('table_num'))
        db.session.add(study)
    
        # Create Peaks and attach to Studies
        peaks = [map(float, y) for y in x.get('peaks')]
        for coordinate in peaks:
            peak=studies.Peak(x=coordinate[0],y=coordinate[1],z=coordinate[2])
            study.peaks.append(peak)
            db.session.add(peak)
        
        # Map features onto studies via a Frequency join table that also stores frequency info
        features=Features(db)
        pmid_frequencies=feature_data[study.pmid]
        for y in range(len(feature_list)):
            if pmid_frequencies[y] > 0.0:
                db.session.add(features.Frequency(study=study,feature=feature_dict[feature_list[y]],frequency=pmid_frequencies[y]))
                feature_dict[feature_list[y]].num_studies+=1
                feature_dict[feature_list[y]].num_activations+=len(peaks)
                  
        # Commit each study record separately. A bit slower, but conserves memory.
        db.session.commit()
