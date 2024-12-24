SELECT TOP 1000
       a.*
  FROM (
        SELECT
              ia.UID                                      AS uid
            , CASE WHEN ib.UserPass IS NULL THEN ''
                                            ELSE ib.UserPass
                                             END          AS password        
            , ia.LastLoginDate                            AS last_login
            , ia.RegDate                                  AS created_datetime
            , CASE WHEN ib.UserName IS NULL THEN ''
                                            ELSE LEFT(ib.UserName,20)
                                             END                       AS username
            , CASE WHEN ia.Birth = '' THEN NULL 
                                        ELSE ia.Birth 
                                        END               AS date_of_birth
            , CASE WHEN ia.Sex IS NULL
                    AND ib.Sex = 'W'     THEN 'Y'
                   WHEN ia.Sex IS NULL
                    AND ib.Sex = 'M'     THEN 'N'
                   WHEN ia.Sex = ''
                    AND ib.Sex = 'W'     THEN 'Y'
                   WHEN ia.Sex = ''
                    AND ib.Sex = 'M'     THEN 'N'
                   WHEN ia.Sex = ''    THEN ib.Sex
                   WHEN ia.Sex = '남성' THEN 'N'
                   WHEN ia.Sex = '여성' THEN 'Y'
                                         ELSE ''
                                         END
                                                          AS gender
            , ia.OutDate                                  AS withdrew_datetime
            , ia.IsBlock                                  AS _is_service_blocked
            -- , CASE WHEN ib.UserID   = ''
            --          OR ib.UserID   IS NULL THEN CONCAT(ia.AM_UserID,ia.uid)
            --                                 ELSE CONCAT(ib.UserID,ia.uid)
            --                                  END
            --                                               AS HelperUserID            
            , CASE WHEN ib.UserID   = ''
                     OR ib.UserID   IS NULL THEN CONCAT(ia.AM_UserID,ia.uid,'@')
                                            ELSE CONCAT(ib.UserID,ia.uid,'@')
                                             END
                                                          AS email

            , CASE WHEN ia.ErrandTel IS NULL
                    AND ia.ErrandTel = ''   THEN LEFT(ia.UserHP,11)
                                            ELSE LEFT(ia.ErrandTel,11) END 
                                                          AS number

            , ia.BlockDate                                AS start_datetime
            , CONVERT(datetime, ia.BlockEndDate)          AS end_datetime
           

            -- , CASE WHEN ia.IsBlock      =  'N'
            --         AND ia.IsOut        =  'N'
            --         AND ia.AM_UserID    <> ''
            --         AND ib.IsRealAuthor =  'Y'  THEN '20' /* 20 정식헬퍼 */
            --        WHEN ia.IsBlock      =  'N'
            --         AND ia.IsOut        =  'N'
            --         AND ib.IsRealAuthor =  'N'  THEN '30' /* 30 임시헬퍼 */
            --        WHEN ia.IsBlock      =  'Y'  THEN '40' /* 40 블락헬퍼 */
            --        WHEN ia.isOut        =  'Y'  THEN '80' /* 80 탈퇴헬퍼 */
            --                                     ELSE '90' /* 90 기타    */
            --                                      END
            --                                               AS helper_grade           
           
           
            -- , CASE 
            --        WHEN ia.S_H IS NULL THEN '00:00'
            --        WHEN ia.S_H = ''    THEN '00:00'
            --       --  WHEN ia.S_H IN ('00')
            --        ELSE CONCAT(CONVERT(varchar(2),ia.S_H),':00') END   AS push_not_allowed_from
            -- , CASE 
            --        WHEN ia.E_H IS NULL THEN '00:00'
            --        WHEN ia.E_H = ''    THEN '00:00'
            --        ELSE CONCAT(CONVERT(varchar(2),ia.E_H),':00') END   AS push_not_allowed_to

            -- , ia.T_INTRODUCE                              AS introduction
            -- , ia.Bank                                     AS bank_code
            -- , ia.BankNum                                  AS bank_number
            
            -- , ia.BankUser                                 AS bank_name
            -- , CASE WHEN ia.T_ADDR1 = ''
            --          OR ia.T_ADDR1 IS NULL THEN ib.Addr1
            --                                ELSE ia.T_ADDR1
            --                                END
            --                                               AS HelperAddr1
            -- , CASE WHEN ia.T_ADDR2 = ''
            --          OR ia.T_ADDR2 IS NULL THEN ib.Addr2
            --                                ELSE ia.T_ADDR2
            --                                END
            --                                               AS HelperAddr2

            -- -- , ia.BlockReason     AS HelperBlockReason

            -- -- , ia.IsOut           AS HelperSecessionYn

            -- , ia.ConPath                                  AS HelperJoinPath
            -- , ia.T_JOINPATH                               AS HelperJoinTerm
            -- , ia.Point                                    AS HelperPoint

            -- , CASE WHEN ia.IsBlock      =  'N'
            --         AND ia.IsOut        =  'N'
            --         AND ia.AM_UserID    <> ''
            --         AND ib.IsRealAuthor =  'Y'  THEN '20' /* 20 정식헬퍼 */
            --        WHEN ia.IsBlock      =  'N'
            --         AND ia.IsOut        =  'N'
            --         AND ib.IsRealAuthor =  'N'  THEN '30' /* 30 임시헬퍼 */
            --        WHEN ia.IsBlock      =  'Y'  THEN '40' /* 40 블락헬퍼 */
            --        WHEN ia.isOut        =  'Y'  THEN '80' /* 80 탈퇴헬퍼 */
            --                                     ELSE '90' /* 90 기타    */
            --                                      END
            --                                               AS HelperGrade

            -- , ia.Cash                                     AS HelperCash

            -- , ia.AlarmErrand                              AS HelperPushGetYn






            -- , CASE WHEN ib.Pic     = ''
            --          OR ib.Pic     IS NULL THEN ia.T_PIC
            --                                ELSE ib.Pic
            --                                END 
            --                                               AS HelperProfilePicturePath
            -- , ia.T_PIC_SSN                                AS HelperIDPicturePath

            -- , CASE WHEN ia.T_JOB   = ''
            --          OR ia.T_JOB   IS NULL THEN ib.Job
            --                                ELSE ia.T_JOB
            --                                END
            --                                               AS HelperJob
            
            -- , ia.T_MISSION                                AS HelperMission
            -- , ia.T_HAPPY                                  AS HelperHappy
            -- , ia.T_MOVE                                   AS HelperMove

            -- , ia.T_TEL                                    AS HelperEmergencyPhone

            -- , ia.SNS_BLOG                                 AS HelperSnsBlog
            -- , ia.SNS_FACEBOOK                             AS HelperSnsFaceBook
            -- , ia.SNS_INSTAGRAM                            AS HelperSnsInstragram
            -- , ia.SNS_TWITTER                              AS HelperSnsTwitter

        FROM na52791588.dbo.M_AM_MEMBER ia /* 멤버기본 */
        LEFT JOIN
             na52791588.dbo.AM_MEMBER   ib /* 멤버기본 */
          ON ia.AM_UserID = ib.UserID

        --  AND ia.BlockDate IS NOT NULL
        
     ) a
 WHERE 1=1
 ORDER BY created_datetime