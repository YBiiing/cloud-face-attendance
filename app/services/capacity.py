from app.errors import AppError

KEY='tasks:reservations'


def reserve(redis,task_id,expires_at,limit=50):
    script="""
    local now=redis.call('TIME');
    redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',now[1]);
    if redis.call('ZCARD',KEYS[1])>=tonumber(ARGV[3]) then return 0 end;
    redis.call('ZADD',KEYS[1],ARGV[2],ARGV[1]);return 1
    """
    try:ok=redis.eval(script,1,KEY,task_id,expires_at.timestamp(),limit)
    except Exception:raise AppError('SERVICE_UNAVAILABLE','任务服务暂时不可用',503) from None
    if not ok:raise AppError('QUEUE_FULL','当前排队人数较多，请稍后再试',503)


def release(redis,task_id):
    try:redis.zrem(KEY,task_id)
    except Exception:pass
