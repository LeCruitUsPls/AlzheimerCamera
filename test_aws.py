#!/usr/bin/env python3
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def test_aws_resources():
    """Test if AWS resources exist and are accessible"""
    
    # Initialize clients
    rekognition = boto3.client('rekognition')
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    
    collection_id = os.getenv('REKOGNITION_COLLECTION_ID', 'alzheimer-faces')
    bucket_name = os.getenv('S3_BUCKET_NAME', 'alzheimer-camera-faces-roy-2025')
    table_name = os.getenv('DYNAMODB_TABLE_NAME', 'alzheimer-persons')
    
    print("Testing AWS Resources...")
    print(f"Region: {os.getenv('AWS_DEFAULT_REGION')}")
    print()
    
    # Test Rekognition collection
    try:
        response = rekognition.describe_collection(CollectionId=collection_id)
        print(f"✅ Rekognition collection '{collection_id}' exists")
        print(f"   Faces: {response['FaceCount']}")
    except rekognition.exceptions.ResourceNotFoundException:
        print(f"❌ Rekognition collection '{collection_id}' not found")
        print("   Creating collection...")
        try:
            rekognition.create_collection(CollectionId=collection_id)
            print(f"✅ Created collection '{collection_id}'")
        except Exception as e:
            print(f"❌ Failed to create collection: {e}")
    except Exception as e:
        print(f"❌ Rekognition error: {e}")
    
    # Test S3 bucket
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ S3 bucket '{bucket_name}' exists")
        
        # List objects
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        object_count = response.get('KeyCount', 0)
        print(f"   Objects: {object_count}")
        
    except Exception as e:
        print(f"❌ S3 bucket error: {e}")
        if "NoSuchBucket" in str(e):
            print("   Creating bucket...")
            try:
                region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
                if region == 'us-east-1':
                    s3.create_bucket(Bucket=bucket_name)
                else:
                    s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                print(f"✅ Created bucket '{bucket_name}'")
            except Exception as create_error:
                print(f"❌ Failed to create bucket: {create_error}")
    
    # Test DynamoDB table
    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"✅ DynamoDB table '{table_name}' exists")
        print(f"   Status: {table.table_status}")
        
        # Count items
        response = table.scan(Select='COUNT')
        item_count = response['Count']
        print(f"   Items: {item_count}")
        
    except Exception as e:
        print(f"❌ DynamoDB table error: {e}")
        if "ResourceNotFoundException" in str(e):
            print("   Creating table...")
            try:
                table = dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=[{'AttributeName': 'person_id', 'KeyType': 'HASH'}],
                    AttributeDefinitions=[{'AttributeName': 'person_id', 'AttributeType': 'S'}],
                    BillingMode='PAY_PER_REQUEST'
                )
                table.wait_until_exists()
                print(f"✅ Created table '{table_name}'")
            except Exception as create_error:
                print(f"❌ Failed to create table: {create_error}")

if __name__ == "__main__":
    test_aws_resources()